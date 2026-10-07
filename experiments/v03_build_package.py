"""Local GLB -> Sims 4 package prototype for the decorative-vase recipe.

The independent_local exporter does not load the Sims 4 Studio Blender addon.
The s4s_local option uses the user's local addon and does not distribute it.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import secrets
import shutil
import struct
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from independent_rcol import Rcol
from v02_catalog_probe import parse_stbl
from v02_identity_clone import (COBJ, OBJD, ROOT, STBL, DEFAULT_DONOR,
                                cobj_refs, h, read_package)

BLENDER = Path(r'C:\Program Files\Blender Foundation\Blender 4.4\blender.exe')
DEFAULT_RECIPE = ROOT / 'recipes/decor_vase.json'
MLOD = 0x01D10F34
MODL = 0x01661233


def find_blender() -> Path | None:
    configured = os.environ.get('CCSTUDIO_BLENDER')
    if configured:
        return Path(configured).expanduser().resolve()
    base = Path(r'C:\Program Files\Blender Foundation')
    installed = sorted(base.glob('Blender 4.4*/blender.exe'), reverse=True) if base.is_dir() else []
    for candidate in (BLENDER, *installed):
        if candidate.is_file():
            return candidate
    found = shutil.which('blender')
    return Path(found).resolve() if found else None


def find_node() -> Path | None:
    configured = os.environ.get('CCSTUDIO_NODE')
    if configured:
        return Path(configured).expanduser().resolve()
    portable = ROOT / 'tools' / ('node.exe' if os.name == 'nt' else 'node')
    if portable.is_file():
        return portable
    found = shutil.which('node')
    return Path(found).resolve() if found else None


def preflight(blender: Path | None, node: Path | None, template: Path,
              donor: Path, mesh_exporter: str, texture_encoder: str) -> dict:
    missing = []
    for label, path in (('Blender', blender),
                        ('blend template', template), ('donor package', donor)):
        if path is None or not path.is_file():
            missing.append(f'{label} not found: {path or "not configured"}')
    scripts = ['ccstudio.py', 'experiments/v02_texture_dst1_probe.py']
    if texture_encoder == 'python':
        scripts.append('experiments/encode_dst1_compatible.py')
    else:
        scripts.append('experiments/encode_dst1_compatible.cjs')
        if node is None or not node.is_file():
            missing.append(f'Node not found: {node or "not configured"}')
    if mesh_exporter == 'independent_local':
        scripts += ['experiments/v04_visual_mlod_export.py',
                    'experiments/v04_proxy_mlod_export.py']
    else:
        scripts += ['experiments/v02_headless_mesh_spike.py']
    for script in scripts:
        if not (ROOT / script).is_file():
            missing.append(f'Script not found: {script}')
    if texture_encoder == 'node':
        for module in ('@s4tk/images', 'silent-dxt-js'):
            if not (ROOT / 'experiments/node_modules' / module).is_dir():
                missing.append(f'DST1 dependency {module} missing: run npm ci in experiments/')
    if importlib.util.find_spec('PIL') is None:
        missing.append('Pillow missing: pip install -r requirements-package.txt')
    elif texture_encoder == 'python':
        try:
            from io import BytesIO
            from PIL import Image
            with BytesIO() as sample:
                Image.new('RGBA', (4, 4), (255, 0, 0, 255)).save(
                    sample, format='DDS', pixel_format='DXT1')
                if sample.getvalue()[84:88] != b'DXT1':
                    raise ValueError('DXT1 FourCC not produced')
        except (OSError, ValueError, ImportError) as error:
            missing.append(f'Pillow DXT1 writer unavailable: {error}')
    return dict(ok=not missing, mesh_exporter=mesh_exporter,
                texture_encoder=texture_encoder,
                blender=str(blender) if blender else None,
                node=str(node) if node else None,
                blend_template=str(template), donor=str(donor), missing=missing)


def load_recipe(path: Path) -> dict:
    recipe = json.loads(path.read_text(encoding='utf-8'))
    if recipe.get('schema_version') != 1 or recipe.get('id') != 'decor_vase':
        raise ValueError('Only schema v1 decorative-vase recipes are supported')
    if recipe.get('mesh_exporter') != 's4s_local':
        raise ValueError('Unsupported mesh exporter; available: s4s_local')
    diffuse = recipe.get('diffuse', {})
    catalog = recipe.get('catalog', {})
    try:
        recipe['diffuse_tgi'] = (int(diffuse['type'], 16), int(diffuse['group'], 16),
                                 int(diffuse['instance'], 16))
        recipe['price_offset'] = int(catalog['price_offset'])
        recipe['base_price'] = int(catalog['base_price'])
        recipe['stbl_locale_count'] = int(catalog['stbl_locale_count'])
        recipe['template_path'] = (ROOT / recipe['blend_template']).resolve()
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f'Invalid recipe fields: {error}') from error
    if (recipe['diffuse_tgi'][:2] != (0x00B2D882, 0x80000000) or
            diffuse.get('fourcc') != 'DST1' or recipe['price_offset'] != 16 or
            recipe['stbl_locale_count'] != 18 or not 0 <= recipe['base_price'] <= 1_000_000):
        raise ValueError('Recipe uses a resource layout unsupported by the current stages')
    return recipe


def mesh_export_command(exporter: str, blender: Path, blend: Path,
                        donor: Path, output: Path) -> list[str]:
    if exporter == 's4s_local':
        return [str(blender), '--background', '--python',
                str(ROOT / 'experiments/v02_headless_mesh_spike.py'), '--',
                '--blend', str(blend), '--template', str(donor), '--output', str(output)]
    raise ValueError(f'Unsupported mesh exporter: {exporter}')


def run(stage: str, command: list[str], output: Path, report: dict) -> None:
    log_path = output / f'{stage}.log'
    with log_path.open('w', encoding='utf-8') as log:
        log.write(' '.join(command) + '\n\n')
        log.flush()
        completed = subprocess.run(command, cwd=ROOT, stdout=log,
                                   stderr=subprocess.STDOUT, text=True)
    report['stages'].append(dict(name=stage, command=command,
                                 exit_code=completed.returncode, log=str(log_path)))
    if completed.returncode:
        raise RuntimeError(f'{stage} failed (exit {completed.returncode}); see {log_path}')


def validate_recipe(donor: Path, recipe: dict) -> dict:
    _, entries = read_package(donor)
    objds = [e for e in entries if e['type'] == OBJD]
    cobjs = [e for e in entries if e['type'] == COBJ]
    diffuses = [e for e in entries if (e['type'], e['group'], e['instance']) ==
                recipe['diffuse_tgi']]
    stbls = [e for e in entries if e['type'] == STBL]
    if (len(objds) != 1 or len(cobjs) != 1 or len(diffuses) != 1 or
            len(stbls) != recipe['stbl_locale_count']):
        raise ValueError('Donor does not match the supported decorative-vase recipe')
    if struct.unpack_from('<I', objds[0]['data'], recipe['price_offset'])[0] != recipe['base_price']:
        raise ValueError(f"Donor OBJD price differs from recipe baseline §{recipe['base_price']}")
    diffuse = diffuses[0]['data']
    if diffuse[:4] != b'DDS ' or diffuse[84:88] != b'DST1':
        raise ValueError('Donor Diffuse must be DST1')
    return dict(sha256=h(donor.read_bytes()), entry_count=len(entries),
                diffuse_tgi=':'.join(f'{part:0{width}X}' for part, width in
                                     zip(recipe['diffuse_tgi'], (8, 8, 16))),
                diffuse_width=struct.unpack_from('<I', diffuse, 16)[0],
                diffuse_height=struct.unpack_from('<I', diffuse, 12)[0])


def audit_final(path: Path, name: str, description: str, price: int,
                recipe: dict, mesh_exporter: str) -> dict:
    _, entries = read_package(path)
    tgis = {(e['type'], e['group'], e['instance']) for e in entries}
    objds = [e for e in entries if e['type'] == OBJD]
    cobjs = [e for e in entries if e['type'] == COBJ]
    stbls = [e for e in entries if e['type'] == STBL]
    if (len(objds) != 1 or len(cobjs) != 1 or
            len(stbls) != recipe['stbl_locale_count']):
        raise ValueError('Final package has unexpected catalog resources')
    actual_price = struct.unpack_from('<I', objds[0]['data'], recipe['price_offset'])[0]
    if actual_price != price:
        raise ValueError(f'Final price {actual_price} != {price}')
    stbl_bases = {e['instance'] & ((1 << 56) - 1) for e in stbls}
    if len(stbl_bases) != 1:
        raise ValueError('STBL locale bases diverged')
    locale_zero = next(e for e in stbls if e['instance'] >> 56 == 0)
    strings, _ = parse_stbl(locale_zero['data'])
    values = {e['value'] for e in strings}
    if name not in values or description not in values:
        raise ValueError('Catalog strings missing from locale-zero STBL')
    missing = [r for r in cobj_refs(cobjs[0]['data']) if r['instance'] and
               (r['type'], r['group'], r['instance']) not in tgis]
    if missing:
        raise ValueError(f'Unresolved COBJ references: {missing}')
    lods = {}
    all_bounds = []
    for entry in entries:
        if entry['type'] != MLOD:
            continue
        rcol = Rcol.parse(entry['data'])
        if rcol.to_bytes() != entry['data']:
            raise ValueError(f"Independent RCOL roundtrip failed for group {entry['group']:08X}")
        meshes = rcol.inspect_mlod()
        lods[f"{entry['group']:08X}"] = [mesh['triangle_count'] for mesh in meshes]
        all_bounds.extend(mesh['bounds'] for mesh in meshes)
    if set(lods) != {'00000000', '00000001', '00010000', '00010001', '00010002'}:
        raise ValueError(f'Unexpected decorative-vase MLOD groups: {sorted(lods)}')
    modls = [entry for entry in entries if entry['type'] == MODL]
    if len(modls) != 1:
        raise ValueError('Expected one MODL resource')
    modl = Rcol.parse(modls[0]['data'])
    embedded = modl.inspect_mlod()
    modl_chunk = next(chunk for chunk in modl.chunks if chunk[:4] == b'MODL')
    modl_bounds = struct.unpack_from('<6f', modl_chunk, 12)
    all_bounds.extend(mesh['bounds'] for mesh in embedded)
    bbox_covers_lods = all(
        modl_bounds[axis] <= bounds[axis] + 1e-5 and
        modl_bounds[axis + 3] >= bounds[axis + 3] - 1e-5
        for bounds in all_bounds for axis in range(3))
    if mesh_exporter == 'independent_local' and not bbox_covers_lods:
        raise ValueError('MODL bounding box does not enclose all MLODs')
    return dict(package_sha256=h(path.read_bytes()), package_bytes=path.stat().st_size,
                resource_count=len(entries), unique_tgi_count=len(tgis),
                shared_stbl_base=True, unresolved_cobj_references=0,
                catalog_name=name, catalog_description=description, price=actual_price,
                independent_rcol_roundtrip=True, lod_triangles=lods,
                modl_embedded_triangles=[mesh['triangle_count'] for mesh in embedded],
                modl_bounds=modl_bounds, modl_bbox_covers_lods=bbox_covers_lods)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, help='Source .glb')
    ap.add_argument('--name', help='Build/Buy catalog name')
    ap.add_argument('--check', action='store_true', help='Report package dependencies as JSON, without building')
    ap.add_argument('--description', default='Generated by CC Studio')
    ap.add_argument('--price', type=int, help='Defaults to recipe base price')
    ap.add_argument('--recipe', type=Path, default=DEFAULT_RECIPE)
    ap.add_argument('--mesh-exporter', choices=('s4s_local', 'independent_local'),
                    help='Override the recipe mesh exporter; independent_local is experimental')
    ap.add_argument('--lod-strategy', choices=('donor-lower', 'generated'),
                    default='donor-lower', help='Experimental: generate lower and proxy LODs')
    ap.add_argument('--proxy-exporter', choices=('existing', 'independent'),
                    default='existing', help='Experimental independent position-only proxy MLOD')
    ap.add_argument('--output', type=Path, help='New output directory')
    ap.add_argument('--blender', type=Path)
    ap.add_argument('--node', type=Path, help='Node runtime for DST1 encoder')
    ap.add_argument('--texture-encoder', choices=('python', 'node'), default='python')
    ap.add_argument('--blend-template', type=Path)
    ap.add_argument('--donor', type=Path)
    ap.add_argument('--rotate-x', type=float, default=0.0)
    ap.add_argument('--rotate-y', type=float, default=0.0)
    ap.add_argument('--rotate-z', type=float, default=0.0)
    args = ap.parse_args()
    try:
        recipe = load_recipe(args.recipe.resolve())
    except (OSError, ValueError) as error:
        ap.error(f'Recipe invalid: {error}')
    template = (args.blend_template or recipe['template_path']).resolve()
    mesh_exporter = args.mesh_exporter or recipe['mesh_exporter']
    if mesh_exporter == 'independent_local' and (
            args.lod_strategy != 'donor-lower' or args.proxy_exporter != 'existing'):
        ap.error('independent_local already builds all LODs; omit LOD/proxy overrides')
    donor = (args.donor or Path(os.environ.get(recipe['donor_env'], str(DEFAULT_DONOR)))).resolve()
    price = recipe['base_price'] if args.price is None else args.price
    blender = args.blender.resolve() if args.blender else find_blender()
    node = args.node.resolve() if args.node else find_node()
    readiness = preflight(blender, node, template, donor, mesh_exporter,
                          args.texture_encoder)
    if args.check:
        print(json.dumps(readiness, indent=2))
        if not readiness['ok']:
            raise SystemExit(1)
        return
    if not readiness['ok']:
        ap.error('; '.join(readiness['missing']))
    if args.input is None or args.name is None:
        ap.error('--input and --name are required for a build')
    source = args.input.resolve()
    if not source.is_file() or source.suffix.lower() != '.glb':
        ap.error('Input must be an existing .glb file')
    assert blender is not None
    if not args.name.strip() or not 0 <= price <= 1_000_000:
        ap.error('Provide a name and a price from 0 to 1,000,000')
    donor_audit = validate_recipe(donor, recipe)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output = (args.output or ROOT / 'output' / f'package_{source.stem}_{stamp}').resolve()
    if output.exists():
        ap.error(f'Output already exists: {output}')
    output.mkdir(parents=True)
    work = output / 'stages'
    work.mkdir()
    report = dict(status='RUNNING', scope='local_private_prototype',
                  input=str(source), input_sha256=h(source.read_bytes()),
                  donor=str(donor), donor_recipe=donor_audit,
                  recipe=dict(id=recipe['id'], path=str(args.recipe.resolve()),
                              mesh_exporter=mesh_exporter,
                              texture_encoder=args.texture_encoder,
                              lod_strategy=('independent_all' if mesh_exporter == 'independent_local'
                                            else args.lod_strategy),
                              proxy_exporter=args.proxy_exporter),
                  blend_template=str(template),
                  catalog=dict(name=args.name, description=args.description, price=price),
                  output=str(output), stages=[])
    report_path = output / 'build_report.json'
    try:
        engine = work / 'engine'
        engine.mkdir()
        run('01_glb_to_blend', [str(blender)] +
            (['--factory-startup'] if mesh_exporter == 'independent_local' else []) +
            ['--background', '--python',
            str(ROOT / 'ccstudio.py'), '--', '--input', str(source),
            '--template', str(template), '--output', str(engine),
            '--rotate-x', str(args.rotate_x), '--rotate-y', str(args.rotate_y),
            '--rotate-z', str(args.rotate_z)], output, report)
        engine_report = json.loads((engine / 'report.json').read_text(encoding='utf-8'))
        if engine_report.get('status') != 'success':
            raise RuntimeError('GLB engine report did not indicate success')
        blend = engine / 'sims_ready.blend'
        basecolor = engine / 'basecolor.png'
        if not blend.is_file() or not basecolor.is_file():
            raise RuntimeError('GLB engine did not produce blend and basecolor')
        mesh = work / '01_mesh.package'
        if mesh_exporter == 'independent_local':
            visual = work / '01_visual.package'
            visual_report = work / 'independent_visual_report.json'
            run('02_independent_visual_lods', [str(blender), '--factory-startup',
                '--background', '--python', str(ROOT / 'experiments/v04_visual_mlod_export.py'),
                '--', '--blend', str(blend), '--input', str(donor),
                '--output', str(visual), '--report', str(visual_report)], output, report)
            visual_audit = json.loads(visual_report.read_text(encoding='utf-8'))
            visual_groups = {group.get('group') for group in visual_audit.get('groups', [])}
            if (visual_audit.get('status') != 'PROGRAMMATIC_PASS' or
                    visual_audit.get('s4s_loaded') or
                    visual_audit.get('changed_resource_count') != 3 or
                    visual_groups != {'00000000', '00000001', 'MODL_EMBEDDED'}):
                raise RuntimeError('Independent visual exporter did not pass its audit')
            proxy_report = work / 'independent_proxy_report.json'
            run('02b_independent_proxy_lods', [str(blender), '--factory-startup',
                '--background', '--python', str(ROOT / 'experiments/v04_proxy_mlod_export.py'),
                '--', '--blend', str(blend), '--input', str(visual),
                '--output', str(mesh), '--report', str(proxy_report), '--all-proxies'],
                output, report)
            proxy_audit = json.loads(proxy_report.read_text(encoding='utf-8'))
            if proxy_audit.get('status') != 'PROGRAMMATIC_PASS' or proxy_audit.get('s4s_loaded'):
                raise RuntimeError('Independent proxy exporter did not pass its audit')
            report['independent_visual_audit'] = visual_audit
            report['independent_proxy_audit'] = proxy_audit
        else:
            run('02_blend_to_mlod', mesh_export_command(mesh_exporter,
                blender, blend, donor, mesh), output, report)
        if mesh_exporter == 's4s_local' and args.lod_strategy == 'generated':
            all_lods = work / '01_mesh_all_lods.package'
            lod_report = work / 'lod_report.json'
            run('02b_generate_lower_lods', [str(blender), '--background', '--python',
                str(ROOT / 'experiments/v03_generate_lods.py'), '--',
                '--blend', str(blend), '--input', str(mesh), '--output', str(all_lods),
                '--report', str(lod_report)], output, report)
            lod_audit = json.loads(lod_report.read_text(encoding='utf-8'))
            if lod_audit.get('status') != 'PROGRAMMATIC_PASS':
                raise RuntimeError('Lower-LOD generator did not pass its audit')
            report['lod_audit'] = lod_audit
            mesh = all_lods
        if mesh_exporter == 's4s_local' and args.proxy_exporter == 'independent':
            independent_proxy = work / '01_mesh_independent_proxy.package'
            proxy_report = work / 'independent_proxy_report.json'
            run('02c_independent_proxy', [str(blender), '--factory-startup',
                '--background', '--python', str(ROOT / 'experiments/v04_proxy_mlod_export.py'),
                '--', '--blend', str(blend), '--input', str(mesh),
                '--output', str(independent_proxy), '--report', str(proxy_report)],
                output, report)
            proxy_audit = json.loads(proxy_report.read_text(encoding='utf-8'))
            if (proxy_audit.get('status') != 'PROGRAMMATIC_PASS' or
                    proxy_audit.get('s4s_loaded')):
                raise RuntimeError('Independent proxy exporter did not pass its audit')
            report['independent_proxy_audit'] = proxy_audit
            mesh = independent_proxy
        textured = work / '02_textured.package'
        run('03_diffuse_dst1', [sys.executable, str(ROOT / 'experiments/v02_texture_dst1_probe.py'),
            '--input', str(mesh), '--image', str(basecolor), '--output', str(textured),
            '--encoder', args.texture_encoder] +
            (['--node', str(node)] if args.texture_encoder == 'node' and node else []) + [
            '--report', str(work / 'texture_report.json'),
            '--diffuse-instance', hex(recipe['diffuse_tgi'][2])], output, report)
        reminted = work / '03_reminted.package'
        run('04_standalone_identity', [sys.executable, str(ROOT / 'experiments/v02_identity_clone.py'),
            '--donor', str(textured), '--output', str(reminted),
            '--report', str(work / 'remint_report.json'),
            '--salt', 'CCStudio-build-' + secrets.token_hex(12)], output, report)
        catalog = work / '04_catalog.package'
        run('05_catalog', [sys.executable, str(ROOT / 'experiments/v02_catalog_probe.py'),
            '--input', str(reminted), '--output', str(catalog),
            '--report', str(work / 'catalog_report.json'), '--name', args.name,
            '--description', args.description], output, report)
        final_stage = catalog
        if price != recipe['base_price']:
            final_stage = work / '05_price.package'
            run('06_price', [sys.executable, str(ROOT / 'experiments/v02_price_probe.py'),
                '--input', str(catalog), '--output', str(final_stage),
                '--report', str(work / 'price_report.json'), '--price', str(price),
                '--expected-old-price', str(recipe['base_price'])],
                output, report)
        package = output / 'CCStudio.package'
        shutil.copyfile(final_stage, package)
        report['final_audit'] = audit_final(package, args.name, args.description,
                                            price, recipe, mesh_exporter)
        report['package'] = str(package)
        report['blend'] = str(blend)
        report['basecolor'] = str(basecolor)
        report['status'] = 'PROGRAMMATIC_PASS'
        report['game_placement'] = 'NOT_TESTED'
        print(f"[PASS] {package}\n[REPORT] {report_path}")
    except Exception as error:
        report['status'] = 'FAILED'
        report['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
