# CC Studio: pesquisa de componentes (2026-10-03)

## Objetivo e estado do projeto

Produto: aplicativo desktop que transforma um modelo 3D texturizado em `.package` de objeto decorativo do The Sims 4. Entrada por foto pode ser acrescentada depois, produzindo um GLB que entra no mesmo pipeline.

O caminho experimental `independent_local` já grava cinco MLODs sem carregar o addon do Sims 4 Studio e passou em três GLBs no teste offline. Ainda não há colocação no jogo de um pacote produzido por esse caminho. A interface executada do código fonte oferece a opção; o executável v0.2 empacotado ainda não a inclui. Ver `V04_INDEPENDENT_MLOD.md`.

## Achados úteis no GitHub

| Componente | Evidência | Decisão para o CC Studio |
| --- | --- | --- |
| [Sims 4 Toolkit Models](https://github.com/sims4toolkit/models) | Implementa leitura/escrita de pacotes e recursos; licença MIT, mas o projeto avisa que está em pré-lançamento. | Manter como referência e dependência dos passos de catálogo já existentes, com versão fixada. Nosso writer e auditoria DBPF/RCOL devem continuar sob nosso controle. |
| [Sims 4 Toolkit Images](https://github.com/sims4toolkit/images) | Processa imagens DST; licença MIT no pacote instalado (`@s4tk/images` 0.2.4). | Aproveitar no encoder DST1 atual. Conferir e guardar licenças transitivas no empacotamento. |
| [sims-package2glb](https://github.com/infinition/sims-package2glb) | Leitor de `package`/RCOL e exportador para glTF, licença MIT. | Referência cruzada de formato e auditoria; não é um exportador pronto de GLB para pacote. |
| [Node single executable applications](https://nodejs.org/api/single-executable-applications.html) | A documentação oficial prevê distribuir aplicativo Node sem Node instalado no computador do usuário; API em desenvolvimento. | Investigar como embutir o encoder DST1 em um helper de distribuição. Priorizar primeiro a conclusão do pipeline de objetos decorativos. |
| [Licença do Blender](https://www.blender.org/about/license/) | Blender pode ser usado e distribuído, sujeito às obrigações GPL; scripts Python publicados como addons têm considerações próprias descritas pela Blender Foundation. | Manter Blender como processo externo detectado pelo aplicativo nesta fase. Antes de incluí-lo no instalador, revisar a forma de distribuição e os avisos/licenças. |

O encoder atual `experiments/encode_dst1_compatible.cjs` usa `@s4tk/images` e `silent-dxt-js`. O `LICENSE` instalado de `silent-dxt-js` também é MIT. O obstáculo prático imediato é o runtime Node no computador de destino, não a ausência de uma implementação DST1.

## Achados no Hugging Face: foto para 3D

| Modelo | Saída e requisito observados | Licença / encaixe |
| --- | --- | --- |
| [Stable Fast 3D](https://huggingface.co/stabilityai/stable-fast-3d), [código](https://github.com/Stability-AI/stable-fast-3d) | Imagem única → GLB com UV e textura; ~6 GB VRAM no exemplo padrão. Suporte Windows é experimental. | Licença comunitária da Stability AI, acesso aos pesos condicionado a aceitar termos; uso comercial tem condições e limite de receita. Melhor encaixe técnico, mas deve ser provedor **opcional** e separado do instalador inicial. |
| [TripoSR](https://huggingface.co/stabilityai/TripoSR), [código](https://github.com/VAST-AI-Research/TripoSR) | Imagem única → malha; opção `--bake-texture` para textura, ~6 GB VRAM padrão. | MIT para código e pesos segundo o repositório e card. Candidato aberto para primeiro protótipo local de foto, depois de confirmar que o GLB gerado tem UV/textura aproveitáveis pelo nosso pipeline. |
| [TRELLIS Image Large](https://huggingface.co/microsoft/TRELLIS-image-large), [código](https://github.com/microsoft/TRELLIS) | Gera ativos 3D; exige NVIDIA com pelo menos 16 GB VRAM, e o código é testado em Linux. | MIT; usar como opção avançada futura, não como requisito do desktop Windows. |
| [Hunyuan3D 2.1](https://huggingface.co/tencent/Hunyuan3D-2.1), [código](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1) | Geometria e textura; projeto informa 29 GB VRAM para ambos. | Licença comunitária específica, com restrições territoriais expressas. Não usar como dependência padrão. |

Esses modelos geram candidatos a GLB; nenhum substitui as etapas de catálogo, MLOD, DST1 e DBPF do CC Studio. Qualidade de malha e textura, licença de pesos e instalação são aspectos separados da viabilidade do pacote no jogo.

## Sequência de desenvolvimento proposta

1. Consolidar o exportador independente de decoração como caminho de produção: corrigir qualquer problema que apareça no primeiro teste integrado de colocação/LOD, mantendo auditoria offline em cada build.
2. Criar uma distribuição do modo `.package`: detectar Blender, incluir scripts/receita/relatórios, resolver o helper DST1 sem exigir instalação manual de Node, e definir uma fonte de template/doador redistribuível. Não distribuir um pacote do jogo sem esclarecer seus direitos.
3. Introduzir uma interface de provedores `imagem → GLB` desacoplada do empacotador. O primeiro candidato de integração é TripoSR pela licença MIT; Stable Fast 3D fica como alternativa opcional com seus próprios termos.
4. Expandir receitas para outras categorias só depois da decoração independente, com campos e MLODs específicos por categoria. Cada receita deve declarar suas limitações e sua origem de recursos.

Critério de produto v1: usuário escolhe um GLB texturizado e recebe um `.package` decorativo instalável por uma interface Windows, com nome, descrição, preço, miniatura e relatório de build; sem configuração de Sims 4 Studio. Foto para 3D é uma entrada opcional posterior.
