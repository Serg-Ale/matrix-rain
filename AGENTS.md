# Guia para agentes de IA — Matrix Rain

## Visão geral

Este é um aplicativo de terminal independente, em transição de "só chuva
digital" para um visualizador de terminal multi-modo (nome definitivo ainda
em aberto — ver issue #1). Usa a biblioteca padrão `curses`; não há servidor,
interface web, gerenciador de pacotes nem dependências de terceiros ainda
(distribuição via `pip`/`pipx` é trabalho futuro — issue #7).

Arquivos versionados:

- `matrix-rain`: ponto de entrada executável — um lançador fino que só ajusta
  `sys.path` e chama `core.cli.run()`. A implementação real vive em `core/` e
  `modes/`.
- `core/`: motor compartilhado por todos os modos.
  - `app.py`: orquestração — ciclo de vida do `curses`, loop principal,
    entrada, resize, cores/desenho compartilhados, painel de controle. A
    classe `App` é o equivalente ao antigo `MatrixRain`.
  - `cli.py`: parsing de argumentos (`parse_args`) e bootstrap do `curses`
    (`run`).
  - `charset.py`: conjuntos de caracteres (Katakana, números, símbolos).
  - `palette.py`: paleta de 256 cores por tema (pré-true-color — ver issue
    #3), sequência do arco-íris, cores de contraste.
- `modes/`: um arquivo por modo de visualização, cada um implementando a
  interface `modes.base.Mode` (`reset(app)`, `render(app)`).
  - `rain.py`: chuva digital — `Column`, grades persistentes de
    caractere/brilho, `RainMode`.
  - `pulse.py`: anéis expansivos — `PulseMode`.
  - `network.py`: campo 3D de nós/links/estrelas — `NetworkMode`.
  - `scanner.py`: radar tático — `ScannerMode`, existe mas **não** está
    registrado no ciclo de modos (era código morto já antes do split modular;
    ver comentário no arquivo). Não o ative sem que isso seja uma decisão de
    produto deliberada.
  - `__init__.py`: registro dos modos — `MODE_ORDER` (ordem do ciclo da tecla
    `m`) e `MODE_CLASSES` (nome → classe).
- `README.md`: documentação voltada a pessoas e exemplos de uso.
- `assets/demo.gif`: demonstração visual usada no README.

Um modo nunca importa `curses` diretamente nem escreve na tela por conta
própria — ele recebe a instância de `App` e usa `app.add_char()`,
`app.get_color_attr()`, `app.get_contrast_attr()`, `app.width`/`app.height`,
etc. Isso é o que torna os módulos de modo testáveis/portáveis sem arrastar
`curses` junto.

## Como executar e validar

Use Python 3.6 ou superior em um terminal UTF-8. A animação requer um TTY
real; ela deliberadamente falha quando a saída é redirecionada.

```bash
# validação estática mínima
python3 -m py_compile matrix-rain core/*.py modes/*.py

# validação da interface de linha de comando (não precisa de TTY)
./matrix-rain --help

# execução interativa manual
./matrix-rain -c green -s 5 -d 7
```

Não existe uma suíte de testes automatizados ainda (ver issue #3 e #6 para os
dois módulos que vão ganhar testes de unidade: motor de cor e presets — o
resto continua exigindo validação manual porque depende de `curses`). Depois
de alterar a renderização ou a interação, faça ao menos uma verificação
manual em um terminal 256 cores:

- confirme que `q`, `Esc` e `Ctrl+C` restauram o terminal;
- redimensione a janela durante a animação;
- teste um tema comum e `--rainbow`;
- em `-S`, confirme que qualquer tecla encerra o programa.
- fora de `-S`, altere velocidade e densidade durante a animação e confira o
  painel persistente de estado.

## Arquitetura e fluxo de execução

`core.cli.parse_args()` define a CLI. `core.cli.run()` trata o atalho
`--help` sem precisar de TTY, converte `-c rainbow`/`-r` numa única
configuração de arco-íris, e roda tudo dentro de `curses.wrapper()`. `App`
(`core/app.py`) é instanciada uma vez por execução e mantém uma instância de
cada modo registrado (`self.modes`) viva pelo processo inteiro — trocar de
modo não destrói o estado do modo anterior (por isso o rain continua "caindo"
em segundo plano enquanto você olha o Network).

Cada `Column` (em `modes/rain.py`) representa uma coluna independente de
chuva, com posição da cabeça, velocidade, tamanho de rastro e atraso de
reaparecimento. `RainMode` mantém duas grades do tamanho do terminal:

- `char_grid[y][x]`: último caractere persistente naquela célula;
- `brightness_grid[y][x]`: brilho de `0` (cabeça branca) a `7` (fim do
  rastro); valores maiores que `NUM_SHADES` não são renderizados.

Em cada frame, `App.run()` processa entrada, resize, limpa a tela, chama
`self.modes[self.active_mode].render(self)` e desenha o painel de controle.
`RainMode.render()` atualiza as colunas e desenha as grades; `PulseMode`
desenha anéis expansivos; `NetworkMode` move uma nuvem 3D de pontos, nós,
links adaptativos com gradiente de profundidade, ramificações, faces
preenchidas em cor complementar e pacotes — tudo isso combinado num único
`render()` por frame (sem separação update/draw explícita, pois o estado é
recalculado durante o próprio desenho). `RainMode._update_column()` é o
núcleo do modo rain: move a cabeça, cria um caractere ao cruzar uma célula,
calcula o gradiente do rastro e reaparece a coluna ao sair da tela.
`RainMode._draw()` não gera caracteres: apenas desenha o estado persistido
nas grades.

Duas exceções assimétricas no dispatch de resize/densidade, preservadas do
comportamento pré-split — não são um acidente, são intencionais:

- `RainMode` sempre acompanha o tamanho do terminal e a densidade
  (`App.handle_resize()`/`App.change_density()` chamam
  `self.modes['rain']` incondicionalmente), mesmo que Rain não seja o modo
  ativo no momento — assim, voltar para Rain nunca mostra um estado
  desatualizado.
- `NetworkMode` só é reinicializado (`reset()`) quando é o modo ativo no
  momento do resize/densidade/ativação — os outros modos não recebem
  nenhum reset especial ao serem ativados.

O modo `network` reinicia `network.frame` ao ser selecionado, mas mantém o
ritmo constante escolhido pelo usuário; não introduza aceleração automática.

No modo `network`, `,` e `.` ajustam `NetworkMode.tempo` de `0.1x` a `1.0x`,
em passos de `0.1x`. `NETWORK_SPEED_SCALE` (em `modes/network.py`) mantém a
velocidade máxima em 20% da escala global: velocidade global 10 equivale à
antiga velocidade global 2.

## Convenções e invariantes importantes

- Preserve a compatibilidade com a biblioteca padrão e Python 3.6+ (o piso
  sobe para 3.11+ quando a issue #6 — presets em TOML — for implementada;
  até lá, mantenha 3.6+). Evite sintaxe ou módulos introduzidos em versões
  posteriores.
- `COLOR_PALETTE` (`core/palette.py`) usa índices xterm de 256 cores e deve
  sempre conter exatamente `NUM_SHADES` (8) entradas por tema. O índice 0 é
  a cabeça branca.
- Os pares de cor 1–8 são reservados ao tema normal; o arco-íris começa no par
  10 e reserva 8 pares por item de `RAINBOW_SEQUENCE`.
- Não remova os `try/except curses.error`: escrever no limite inferior/direito
  do terminal e o suporte de cores variam entre emuladores.
- Mantenha `width - 1` ao criar colunas em `RainMode`. É uma proteção
  intencional para caracteres Katakana de largura ambígua e bordas de
  `curses`.
- O caminho de saída deve continuar restaurando cursor e atributos ANSI no
  bloco `finally` de `core.cli.run()`.
- `density` controla a quantidade de fluxos ativos em `RainMode` e também o
  atraso de reaparecimento; `speed` controla a velocidade-base de cada
  coluna, que recebe variação aleatória.
- Fora do modo protetor de tela, `W`/`S` e `A`/`D` (ou as setas, `+`/`-` e
  `[`/`]`) ajustam velocidade e densidade; `t` alterna temas, `r` alterna
  arco-íris, `m` alterna os visualizadores e `h` mostra o painel. `p` alterna
  sua visibilidade.
- Um modo nunca chama `curses` diretamente nem acessa `app.stdscr` fora dos
  helpers já expostos por `App` — exceção histórica: `RainMode._draw()`
  escreve em `app.stdscr.addstr()` diretamente e por isso `modes/rain.py`
  importa `curses` só para capturar `curses.error` ao redor dessa escrita,
  replicando o comportamento pré-split; não generalize esse padrão (nem o
  `import curses`) para outros modos sem necessidade.

## Alterações comuns

- **Novo tema:** acrescente 8 cores a `COLOR_PALETTE` (`core/palette.py`),
  exponha-o nas escolhas da CLI (isso já acontece automaticamente via
  `core.cli.parse_args()`) e atualize o README. Inclua-o em
  `RAINBOW_SEQUENCE` somente se ele fizer sentido no ciclo arco-íris.
- **Ajuste de estética do Rain:** prefira alterar `RainMode._random_speed`,
  `_random_trail_length`, `_update_column` ou `_respawn_column`; não misture
  estado de animação com `_draw`.
- **Novo visualizador:** crie um arquivo em `modes/`, implemente uma classe
  que estenda `modes.base.Mode` (`reset(app)`, `render(app)`), e registre-a
  em `MODE_CLASSES`/`MODE_ORDER` (`modes/__init__.py`). Reuse
  `app.base_speed`, `app.density` e `app.get_color_attr()` para manter os
  controles consistentes com os outros modos.
- **Novo argumento:** implemente-o em `core.cli.parse_args()`, passe-o por
  `core.cli._main()` a `App`, e documente-o no README.

## Limites conhecidos

- A fidelidade visual depende do emulador, fonte monoespaçada com Katakana e
  suporte a UTF-8/256 cores.
- Não há teste automatizado para a interface `curses`; alterações visuais
  exigem validação manual interativa.
- `LATIN` está definido, mas não faz parte de `MATRIX_CHARS`; só o inclua se a
  mudança de estética for intencional.
- `modes/scanner.py` (`ScannerMode`) não está registrado em `MODE_CLASSES` —
  código pré-existente, preservado mas inerte (ver comentário no arquivo).

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
