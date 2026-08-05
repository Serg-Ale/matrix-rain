# Guia para agentes de IA — Matrix Rain

## Visão geral

Este é um aplicativo de terminal independente. O executável Python
[`matrix-rain`](./matrix-rain) cria uma animação de "chuva digital" usando a
biblioteca padrão `curses`; não há servidor, interface web, gerenciador de
pacotes nem dependências de terceiros.

Arquivos versionados:

- `matrix-rain`: código-fonte e ponto de entrada executável.
- `README.md`: documentação voltada a pessoas e exemplos de uso.
- `assets/demo.gif`: demonstração visual usada no README.

## Como executar e validar

Use Python 3.6 ou superior em um terminal UTF-8. A animação requer um TTY
real; ela deliberadamente falha quando a saída é redirecionada.

```bash
# validação estática mínima
python3 -m py_compile matrix-rain

# validação da interface de linha de comando (não precisa de TTY)
./matrix-rain --help

# execução interativa manual
./matrix-rain -c green -s 5 -d 7
```

Não existe uma suíte de testes automatizados. Depois de alterar a renderização
ou a interação, faça ao menos uma verificação manual em um terminal 256 cores:

- confirme que `q`, `Esc` e `Ctrl+C` restauram o terminal;
- redimensione a janela durante a animação;
- teste um tema comum e `--rainbow`;
- em `-S`, confirme que qualquer tecla encerra o programa.
- fora de `-S`, altere velocidade e densidade durante a animação e confira o
  painel persistente de estado.

## Arquitetura e fluxo de execução

`parse_args()` define a CLI. `main()` converte `-c rainbow` ou `-r` em uma
única configuração de arco-íris, instancia `MatrixRain` e a execução é
encapsulada por `curses.wrapper()`.

Cada `Column` representa uma coluna independente de chuva, com posição da
cabeça, velocidade, tamanho de rastro e atraso de reaparecimento. `MatrixRain`
mantém duas grades do tamanho do terminal:

- `char_grid[y][x]`: último caractere persistente naquela célula;
- `brightness_grid[y][x]`: brilho de `0` (cabeça branca) a `7` (fim do
  rastro); valores maiores que `NUM_SHADES` não são renderizados.

Em cada frame, `run()` processa entrada, resize, limpa a tela, despacha o modo
ativo e atualiza o `curses`. `rain` atualiza as colunas e desenha as grades;
`pulse` desenha anéis expansivos; `network` move uma nuvem 3D de pontos, nós,
links adaptativos com gradiente de profundidade, ramificações, faces preenchidas
em cor complementar e pacotes. `_update_column()` é o núcleo
do modo rain: move a cabeça, cria um caractere ao cruzar uma célula, calcula o
gradiente do rastro e reaparece a coluna ao sair da tela. `_draw()` não gera
caracteres: apenas desenha o estado persistido nas grades.

O modo `network` reinicia `network_frame` ao ser selecionado, mas mantém o
ritmo constante escolhido pelo usuário; não introduza aceleração automática.

No modo `network`, `,` e `.` ajustam `network_tempo` de `0.1x` a `1.0x`, em
passos de `0.1x`. `NETWORK_SPEED_SCALE` mantém a velocidade máxima em 20% da
escala global: velocidade global 10 equivale à antiga velocidade global 2.

## Convenções e invariantes importantes

- Preserve a compatibilidade com a biblioteca padrão e Python 3.6+. Evite
  sintaxe ou módulos introduzidos em versões posteriores.
- `COLOR_PALETTE` usa índices xterm de 256 cores e deve sempre conter
  exatamente `NUM_SHADES` (8) entradas por tema. O índice 0 é a cabeça branca.
- Os pares de cor 1–8 são reservados ao tema normal; o arco-íris começa no par
  10 e reserva 8 pares por item de `RAINBOW_SEQUENCE`.
- Não remova os `try/except curses.error`: escrever no limite inferior/direito
  do terminal e o suporte de cores variam entre emuladores.
- Mantenha `width - 1` ao criar colunas. É uma proteção intencional para
  caracteres Katakana de largura ambígua e bordas de `curses`.
- O caminho de saída deve continuar restaurando cursor e atributos ANSI no
  bloco `finally` do ponto de entrada.
- `density` controla a quantidade de fluxos ativos e também o atraso de
  reaparecimento; `speed` controla a velocidade-base de cada coluna, que
  recebe variação aleatória.
- Fora do modo protetor de tela, `W`/`S` e `A`/`D` (ou as setas, `+`/`-` e
  `[`/`]`) ajustam velocidade e densidade; `t` alterna temas, `r` alterna
  arco-íris, `m` alterna os visualizadores e `h` mostra o painel. `p` alterna
  sua visibilidade.

## Alterações comuns

- **Novo tema:** acrescente 8 cores a `COLOR_PALETTE`, exponha-o nas escolhas
  da CLI (isso já acontece automaticamente) e atualize o README. Inclua-o em
  `RAINBOW_SEQUENCE` somente se ele fizer sentido no ciclo arco-íris.
- **Ajuste de estética:** prefira alterar `_random_speed`,
  `_random_trail_length`, `_update_column` ou `_respawn_column`; não misture
  estado de animação com `_draw`.
- **Novo visualizador:** registre o modo em `VISUALIZER_MODES`, implemente seu
  desenho isolado e conecte-o no despacho de `run()`. Reuse `base_speed`,
  `density` e `_get_color_attr()` para manter os controles consistentes.
- **Novo argumento:** implemente-o em `parse_args()`, passe-o por `main()` a
  `MatrixRain` e documente-o no README.

## Limites conhecidos

- A fidelidade visual depende do emulador, fonte monoespaçada com Katakana e
  suporte a UTF-8/256 cores.
- Não há teste automatizado para a interface `curses`; alterações visuais
  exigem validação manual interativa.
- `LATIN` está definido, mas não faz parte de `MATRIX_CHARS`; só o inclua se a
  mudança de estética for intencional.

## Agent skills

### Issue tracker

Issues vivem no GitHub, em `Serg-Ale/matrix-rain`, via `gh` CLI. Veja
`docs/agents/issue-tracker.md`.

### Triage labels

Labels padrão (`needs-triage`, `needs-info`, `ready-for-agent`,
`ready-for-human`, `wontfix`). Veja `docs/agents/triage-labels.md`.

### Domain docs

Layout single-context (`CONTEXT.md` + `docs/adr/` na raiz). Veja
`docs/agents/domain.md`.
