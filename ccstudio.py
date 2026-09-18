"""
CC Studio Prototype v0.1 — kill-test

Robô feio que repete AUTOMATICAMENTE o processo manual ja validado no Blender:

    input.glb
    -> cleanup
    -> poly reduction
    -> encaixe no template decor_vase
    -> preservacao da estrutura Sims
    -> correcao de UV
    -> extracao de Base Color
    -> sims_ready.blend

NAO gera .package. NAO tem UI. NAO generaliza para outros objetos/templates.
Se der vontade de "melhorar", pare e entregue o script feio.

Uso (obrigatoriamente headless):

    blender.exe --background --python ccstudio.py -- \
        --input input.glb \
        --template templates/decor_vase/template.blend \
        --output output/

Nenhuma operacao pode depender de uma area VIEW_3D ativa (foi o IndexError:
VIEW_3D que quebrou o teste manual). Onde uma op normalmente precisaria de
contexto de tela, usamos bpy.data / bmesh ou context override explicito.
"""

import bpy
import bmesh
import sys
import os
import json
import argparse
from mathutils import Vector


# ---------------------------------------------------------------------------
# constantes de recipe do v0.1 (pertencem ao template decor_vase, nao ao codigo)
# ---------------------------------------------------------------------------
TARGET_MESH_NAME = "s4studio_mesh_1"     # target do template decor_vase
CUT_PROP_NAME = "Cut"                    # custom property a preservar
SOURCE_UV_NAME = "CCSTUDIO_SOURCE_UV"    # nome inequivoco p/ o UV de origem
OLD_GEO_GROUP = "CCSTUDIO_TEMPLATE_OLD"  # vertex group da geometria antiga
SIMS_UV_NAME = "uv_0"                    # UV usado pelo Sims
DECIMATE_TARGET_FACES = 6000
DECIMATE_WARN_FACES = 6500


# ---------------------------------------------------------------------------
# logging feio e report
# ---------------------------------------------------------------------------
def log(msg):
    print(msg, flush=True)


class PipelineError(Exception):
    """Erro que aborta o pipeline com um stage identificavel."""

    def __init__(self, stage, message):
        super().__init__(message)
        self.stage = stage
        self.message = message


def write_report(output_dir, data):
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def fail(output_dir, stage, message):
    """Escreve report de erro e encerra com codigo != 0."""
    log("[FAIL] stage=%s :: %s" % (stage, message))
    write_report(output_dir, {"status": "error", "stage": stage, "message": message})
    sys.exit(1)


# ---------------------------------------------------------------------------
# helpers de geometria
# ---------------------------------------------------------------------------
def world_bbox(obj):
    """Bounding box do objeto em coordenadas de mundo (min, max) como Vectors."""
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    mn = Vector((min(c.x for c in corners),
                 min(c.y for c in corners),
                 min(c.z for c in corners)))
    mx = Vector((max(c.x for c in corners),
                 max(c.y for c in corners),
                 max(c.z for c in corners)))
    return mn, mx


def bbox_dims(mn, mx):
    return Vector((mx.x - mn.x, mx.y - mn.y, mx.z - mn.z))


def face_count(obj):
    return len(obj.data.polygons)


# ---------------------------------------------------------------------------
# argumentos (apenas o que vem depois de "--")
# ---------------------------------------------------------------------------
def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    p = argparse.ArgumentParser(prog="ccstudio.py")
    p.add_argument("--input", required=True, help="input.glb")
    p.add_argument("--template", required=True, help="template.blend do decor_vase")
    p.add_argument("--output", required=True, help="pasta de output/")
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# 1. abrir template
# ---------------------------------------------------------------------------
def open_template(template_path, output_dir):
    log("[CCStudio] Loading template...")
    if not os.path.isfile(template_path):
        fail(output_dir, "open_template", "template not found: %s" % template_path)

    # abre o .blend do template diretamente (substitui a cena inteira)
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(template_path))

    target = bpy.data.objects.get(TARGET_MESH_NAME)
    if target is None or target.type != "MESH":
        fail(output_dir, "open_template",
             "target mesh '%s' not found in template" % TARGET_MESH_NAME)

    # registrar estado ORIGINAL antes de qualquer alteracao
    cut_value = target.get(CUT_PROP_NAME, None)
    custom_props = {k: target[k] for k in target.keys() if not k.startswith("_")}
    uv_layers = [uv.name for uv in target.data.uv_layers]
    mn, mx = world_bbox(target)

    info = {
        "target_name": target.name,
        "cut_value": cut_value,
        "custom_props": custom_props,
        "uv_layers": uv_layers,
        "bbox_min": list(mn),
        "bbox_max": list(mx),
        "dims": list(bbox_dims(mn, mx)),
    }
    log("[PASS] Target: %s" % target.name)
    log("[PASS] Cut: %s" % str(cut_value))
    log("[INFO] Template UV layers: %s" % uv_layers)
    return target, info


# ---------------------------------------------------------------------------
# 2. importar GLB
# ---------------------------------------------------------------------------
def import_glb(input_path, output_dir):
    log("[CCStudio] Importing GLB...")
    if not os.path.isfile(input_path):
        fail(output_dir, "import_glb", "input not found: %s" % input_path)

    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(input_path))
    after = set(bpy.data.objects)
    new_objs = list(after - before)

    # ignorar EMPTY / CAMERA / LIGHT -> so meshes novas
    new_meshes = [o for o in new_objs if o.type == "MESH"]
    new_empties = [o for o in new_objs if o.type == "EMPTY"]

    if len(new_meshes) == 0:
        fail(output_dir, "import_glb", "no mesh found in GLB")
    if len(new_meshes) > 1:
        fail(output_dir, "import_glb", "v0.1 supports only single-mesh GLB files")

    source = new_meshes[0]
    log("[PASS] Mesh found: %s" % source.name)
    log("[INFO] Faces: %d" % face_count(source))
    return source, new_empties


# ---------------------------------------------------------------------------
# 3. preservar referencia ao UV DE ORIGEM (detectar por origem, nao por nome)
# ---------------------------------------------------------------------------
def secure_source_uv(source, output_dir):
    log("[CCStudio] Detecting UV...")
    uvs = source.data.uv_layers
    if len(uvs) == 0:
        fail(output_dir, "source_uv", "source mesh has no UV layer")

    # detectar por origem: UV marcado como render -> ativo -> primeiro valido.
    # active_render e uma flag por-camada, nao um atributo da colecao.
    render_uv = next((u for u in uvs if getattr(u, "active_render", False)), None)
    uv = render_uv or uvs.active or uvs[0]
    real_name = uv.name
    uv.name = SOURCE_UV_NAME  # renomeia ANTES de qualquer Join
    log("[PASS] Source UV found: %s (renamed -> %s)" % (real_name, SOURCE_UV_NAME))
    return real_name


# ---------------------------------------------------------------------------
# 4. encontrar e extrair Base Color
# ---------------------------------------------------------------------------
def _find_base_color_image(obj):
    for slot in obj.material_slots:
        mat = slot.material
        if not mat or not mat.use_nodes:
            continue
        for node in mat.node_tree.nodes:
            if node.type != "BSDF_PRINCIPLED":
                continue
            base = node.inputs.get("Base Color")
            if base is None or not base.is_linked:
                continue
            # segue o link ate achar um no de imagem
            visited = set()
            stack = [l.from_node for l in base.links]
            while stack:
                n = stack.pop()
                if n in visited:
                    continue
                visited.add(n)
                if n.type == "TEX_IMAGE" and n.image is not None:
                    return n.image
                for inp in n.inputs:
                    for l in inp.links:
                        stack.append(l.from_node)
    return None


def extract_base_color(source, output_dir):
    log("[CCStudio] Extracting Base Color...")
    img = _find_base_color_image(source)
    if img is None:
        fail(output_dir, "base_color", "no Base Color image found on source material")

    os.makedirs(output_dir, exist_ok=True)
    out_png = os.path.join(output_dir, "basecolor.png")

    # imagem pode estar embutida no GLB (packed) -> forcar save como PNG
    try:
        img.file_format = "PNG"
        img.filepath_raw = out_png
        img.save()
    except Exception as e:
        # fallback: save_render usando as settings da cena
        try:
            img.save_render(filepath=out_png)
        except Exception as e2:
            fail(output_dir, "base_color",
                 "failed to save basecolor.png: %s / %s" % (e, e2))

    if not os.path.isfile(out_png):
        fail(output_dir, "base_color", "basecolor.png was not written")
    log("[PASS] basecolor.png")
    return out_png


# ---------------------------------------------------------------------------
# 5. limpeza de transform (desparentear + apply)
# ---------------------------------------------------------------------------
def clean_transform(source):
    log("[CCStudio] Cleaning transform...")
    # desparentear preservando matrix_world
    if source.parent is not None:
        world = source.matrix_world.copy()
        source.parent = None
        source.matrix_world = world

    # aplicar loc/rot/scale via override explicito (sem depender de VIEW_3D)
    bpy.ops.object.select_all(action="DESELECT")
    source.select_set(True)
    bpy.context.view_layer.objects.active = source
    with bpy.context.temp_override(active_object=source,
                                   selected_objects=[source],
                                   selected_editable_objects=[source]):
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    log("[PASS] transform applied")


# ---------------------------------------------------------------------------
# 6. auto-fit para decor_vase (primeiro passo "de recipe")
# ---------------------------------------------------------------------------
def auto_fit(source, target, report):
    log("[CCStudio] Fitting mesh...")
    t_min, t_max = world_bbox(target)
    t_dims = bbox_dims(t_min, t_max)

    s_min, s_max = world_bbox(source)
    s_dims = bbox_dims(s_min, s_max)

    report["source_dimensions_before"] = list(s_dims)
    report["template_dimensions"] = list(t_dims)

    if s_dims.z <= 1e-9 or t_dims.z <= 1e-9:
        raise PipelineError("auto_fit", "degenerate Z dimension during fit")

    # escala UNIFORME pela altura Z (nunca deformar X/Y/Z separadamente)
    scale = t_dims.z / s_dims.z
    source.scale = source.scale * scale
    bpy.context.view_layer.update()

    # recalcular bbox pos-escala p/ posicionar
    s_min, s_max = world_bbox(source)
    s_center = (s_min + s_max) * 0.5
    t_center = (t_min + t_max) * 0.5

    # centralizar X/Y no template, alinhar base ao Z minimo do template
    dx = t_center.x - s_center.x
    dy = t_center.y - s_center.y
    dz = t_min.z - s_min.z
    source.location = source.location + Vector((dx, dy, dz))
    bpy.context.view_layer.update()

    s_min, s_max = world_bbox(source)
    report["source_dimensions_after"] = list(bbox_dims(s_min, s_max))
    log("[PASS] fit (scale=%.4f)" % scale)


# ---------------------------------------------------------------------------
# 7. polygon reduction
# ---------------------------------------------------------------------------
def decimate(source, output_dir, report):
    log("[CCStudio] Decimating...")
    faces_before = face_count(source)
    report["faces_before"] = faces_before

    if faces_before <= DECIMATE_TARGET_FACES:
        log("[INFO] %d faces <= %d, skipping decimate" %
            (faces_before, DECIMATE_TARGET_FACES))
        report["faces_after"] = faces_before
        return faces_before, faces_before

    ratio = DECIMATE_TARGET_FACES / float(faces_before)
    mod = source.modifiers.new(name="CCSTUDIO_DECIMATE", type="DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = ratio
    with bpy.context.temp_override(active_object=source,
                                   selected_objects=[source],
                                   selected_editable_objects=[source]):
        bpy.ops.object.modifier_apply(modifier=mod.name)

    faces_after = face_count(source)
    report["faces_after"] = faces_after
    log("[INFO] %d -> %d" % (faces_before, faces_after))

    if faces_after == 0:
        fail(output_dir, "decimate", "decimate produced 0 faces")
    if faces_after > DECIMATE_WARN_FACES:
        log("[WARN] faces_after (%d) > %d" % (faces_after, DECIMATE_WARN_FACES))
    return faces_before, faces_after


# ---------------------------------------------------------------------------
# 8 + 9. marcar geometria antiga, join, remover geometria antiga
# ---------------------------------------------------------------------------
def mark_join_and_clean(source, target, output_dir):
    log("[CCStudio] Removing old template geometry...")

    # 9.1 marcar TODA a geometria original do template num vertex group
    if OLD_GEO_GROUP in target.vertex_groups:
        target.vertex_groups.remove(target.vertex_groups[OLD_GEO_GROUP])
    grp = target.vertex_groups.new(name=OLD_GEO_GROUP)
    old_vert_count = len(target.data.vertices)
    grp.add(list(range(old_vert_count)), 1.0, "REPLACE")
    log("[INFO] verts before mark: %d" % old_vert_count)

    # 8. join: target ATIVO, source entra no target
    bpy.ops.object.select_all(action="DESELECT")
    source.select_set(True)
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    with bpy.context.temp_override(active_object=target,
                                   selected_objects=[target, source],
                                   selected_editable_objects=[target, source]):
        bpy.ops.object.join()
    # apos o join, source deixou de existir; target permanece
    verts_after_join = len(target.data.vertices)
    log("[INFO] verts after join: %d" % verts_after_join)

    # 9.3 deletar os vertices marcados como geometria antiga (via bmesh, headless)
    me = target.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    dvert_lay = bm.verts.layers.deform.active
    grp_index = target.vertex_groups[OLD_GEO_GROUP].index

    to_del = []
    if dvert_lay is not None:
        for v in bm.verts:
            if grp_index in v[dvert_lay]:
                to_del.append(v)
    bmesh.ops.delete(bm, geom=to_del, context="VERTS")
    bm.to_mesh(me)
    bm.free()
    me.update()

    verts_removed = verts_after_join - len(me.vertices)
    log("[INFO] verts removed: %d" % verts_removed)

    # limpar o vertex group auxiliar
    if OLD_GEO_GROUP in target.vertex_groups:
        target.vertex_groups.remove(target.vertex_groups[OLD_GEO_GROUP])

    if len(me.vertices) == 0:
        fail(output_dir, "remove_old_geo",
             "all vertices removed -- imported geometry lost")
    return old_vert_count, verts_after_join, verts_removed


# ---------------------------------------------------------------------------
# 10. normalizar UV para o Sims (CCSTUDIO_SOURCE_UV -> uv_0)
# ---------------------------------------------------------------------------
def normalize_uv(target, output_dir):
    log("[CCStudio] Normalizing UV...")
    me = target.data
    src = me.uv_layers.get(SOURCE_UV_NAME)
    if src is None:
        fail(output_dir, "normalize_uv",
             "source UV '%s' missing after join" % SOURCE_UV_NAME)

    dst = me.uv_layers.get(SIMS_UV_NAME)
    if dst is None:
        # nao existe uv_0 (nao deveria acontecer no decor_vase) -> cria
        dst = me.uv_layers.new(name=SIMS_UV_NAME)

    if len(src.data) != len(dst.data):
        fail(output_dir, "normalize_uv",
             "UV loop count mismatch: src=%d dst=%d" %
             (len(src.data), len(dst.data)))

    for i in range(len(src.data)):
        dst.data[i].uv = src.data[i].uv

    # uv_0 deve permanecer o UV ativo/render usado pelo Sims
    for i, uv in enumerate(me.uv_layers):
        if uv.name == SIMS_UV_NAME:
            me.uv_layers.active_index = i
            uv.active_render = True

    # checks obrigatorios
    if len(dst.data) == 0:
        fail(output_dir, "normalize_uv", "uv_0 is empty after copy")
    if len(dst.data) != len(me.loops):
        fail(output_dir, "normalize_uv",
             "uv_0 loop count (%d) != mesh loops (%d)" %
             (len(dst.data), len(me.loops)))
    log("[PASS] source UV -> uv_0")


# ---------------------------------------------------------------------------
# 11. material apenas para preview (opcional)
# ---------------------------------------------------------------------------
def preview_material(target, basecolor_path):
    log("[CCStudio] Building preview material (optional)...")
    try:
        mat = bpy.data.materials.new(name="CCSTUDIO_PREVIEW")
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(basecolor_path, check_existing=True)
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        # nao apagar materiais do target; so garantir um slot de preview
        if len(target.data.materials) == 0:
            target.data.materials.append(mat)
        else:
            target.data.materials[0] = mat
        log("[PASS] preview material")
    except Exception as e:
        log("[WARN] preview material skipped: %s" % e)


# ---------------------------------------------------------------------------
# 12. QA minimo
# ---------------------------------------------------------------------------
def qa(target, template_info, basecolor_path, output_dir, report):
    log("[CCStudio] QA...")

    # CHECK 1: existe exatamente um s4studio_mesh_1
    matches = [o for o in bpy.data.objects
               if o.name == TARGET_MESH_NAME and o.type == "MESH"]
    if len(matches) != 1:
        fail(output_dir, "qa", "expected exactly one %s, found %d" %
             (TARGET_MESH_NAME, len(matches)))

    # CHECK 2: Cut/custom property preservado
    cut_now = target.get(CUT_PROP_NAME, None)
    cut_orig = template_info["cut_value"]
    if cut_now != cut_orig:
        fail(output_dir, "qa", "Cut changed: %s -> %s" % (cut_orig, cut_now))
    report["cut_preserved"] = True

    # CHECK 3: face count > 0 e <= limite tolerado
    fc = face_count(target)
    if fc <= 0:
        fail(output_dir, "qa", "final face count is %d" % fc)
    if fc > DECIMATE_WARN_FACES:
        log("[WARN] final face count %d > %d" % (fc, DECIMATE_WARN_FACES))

    # CHECK 4: uv_0 existe e nao vazio
    uv0 = target.data.uv_layers.get(SIMS_UV_NAME)
    if uv0 is None or len(uv0.data) == 0:
        fail(output_dir, "qa", "uv_0 missing or empty")

    # CHECK 5: basecolor.png existe
    if not os.path.isfile(basecolor_path):
        fail(output_dir, "qa", "basecolor.png missing")

    # CHECK 6: mesh final nao e EMPTY
    if target.type != "MESH" or len(target.data.vertices) == 0:
        fail(output_dir, "qa", "final target is empty")

    # CHECK 7: bounding box com dimensoes > 0
    mn, mx = world_bbox(target)
    dims = bbox_dims(mn, mx)
    if dims.x <= 0 or dims.y <= 0 or dims.z <= 0:
        fail(output_dir, "qa", "final bbox has zero dimension: %s" % list(dims))

    log("[PASS] All checks")


# ---------------------------------------------------------------------------
# 13. salvar
# ---------------------------------------------------------------------------
def save_output(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    out_blend = os.path.join(output_dir, "sims_ready.blend")
    # nunca sobrescrever template/input: salvamos SEMPRE num caminho novo
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out_blend), copy=True)
    log("[CCStudio] Saved: %s" % out_blend)
    return out_blend


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    args = parse_args()
    output_dir = os.path.abspath(args.output)

    report = {"status": "success"}
    try:
        # 1
        target, template_info = open_template(args.template, output_dir)

        # 2
        source, _empties = import_glb(args.input, output_dir)
        report["source_mesh"] = source.name

        # 3
        real_uv = secure_source_uv(source, output_dir)
        report["source_uv"] = real_uv
        report["target_uv"] = SIMS_UV_NAME

        # 4
        basecolor_path = extract_base_color(source, output_dir)
        report["basecolor_extracted"] = True

        # 5
        clean_transform(source)

        # 6
        auto_fit(source, target, report)

        # 7
        decimate(source, output_dir, report)

        # 8 + 9
        mark_join_and_clean(source, target, output_dir)

        # 10
        normalize_uv(target, output_dir)

        # 11 (opcional)
        preview_material(target, basecolor_path)

        # 12
        report["target_mesh"] = TARGET_MESH_NAME
        qa(target, template_info, basecolor_path, output_dir, report)

        # 13
        save_output(output_dir)

    except PipelineError as e:
        fail(output_dir, e.stage, e.message)
    except SystemExit:
        raise  # fail() ja escreveu o report de erro
    except Exception as e:
        import traceback
        traceback.print_exc()
        fail(output_dir, "unexpected", "%s: %s" % (type(e).__name__, e))

    write_report(output_dir, report)
    log("[CCStudio] report.json written (success)")


if __name__ == "__main__":
    main()
