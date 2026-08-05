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
  - `app.py`: orquestração — ciclo de vida do `curses` (só entrada, resize e
    tela alternativa — ver `screen.py` abaixo), loop principal,
    cores/desenho compartilhados, painel de controle. A classe `App` é o
    equivalente ao antigo `MatrixRain`.
  - `cli.py`: parsing de argumentos (`parse_args`) e bootstrap do `curses`
    (`run`).
  - `charset.py`: conjuntos de caracteres (Katakana, números, símbolos).
  - `color.py`: motor de cor puro — sem `curses`, sem I/O, 100% testável
    (`tests/test_color.py`). Detecção de true color via `COLORTERM`,
    gradiente contínuo RGB, conversão de índice 256 → RGB e o inverso
    (snap determinístico), e a sequência ANSI final (`ansi_fg`).
  - `palette.py`: paleta de 256 cores por tema (a mesma de sempre — ainda é
    o piso de qualidade do fallback) e `theme_gradient_stops()`, que
    converte essas 8 cores por tema em pontos de controle RGB para o
    gradiente contínuo.
  - `screen.py`: o único lugar que escreve na tela de verdade. Mantém um
    buffer de frame e emite ANSI bruto (true color ou fallback 256,
    conforme `App.truecolor`) — ver "Motor de cor" abaixo para o porquê.
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
- `tests/`: testes de unidade (stdlib `unittest`) para a lógica pura de
  `core/color.py` e `core/palette.py`. Nada que dependa de `curses` é
  testado automaticamente — ver "Como executar e validar".
- `README.md`: documentação voltada a pessoas e exemplos de uso.
- `assets/demo.gif`: demonstração visual usada no README.

Um modo nunca importa `curses` nem escreve na tela por conta própria — ele
recebe a instância de `App` e usa `app.add_char()`, `app.get_color()`,
`app.get_contrast_color()`, `app.width`/`app.height`, etc. Isso é o que
torna os módulos de modo testáveis/portáveis sem arrastar `curses` junto.
Não há mais exceção para isso: antes da issue #3, `RainMode._draw()`
escrevia em `app.stdscr.addstr()` diretamente; agora ela passa por
`app.add_char()` como todo mundo, porque o próprio `curses` não desenha
mais nada (ver "Motor de cor" abaixo).

## Motor de cor

Antes da issue #3, cores vinham de pares de cor do `curses`
(`curses.init_pair`/`curses.color_pair`), limitados à paleta de 256 cores —
o motivo é técnico: `curses` só expõe true color quando o `terminfo`
declara `COLORS >= 16777216`, o que praticamente nenhum terminal comum
anuncia mesmo suportando 24-bit de verdade. Por isso o desenho não passa
mais por `curses` de jeito nenhum: `curses` cuida só de entrada
(`stdscr.getch()`), resize (`stdscr.getmaxyx()`) e da tela alternativa
(via `curses.wrapper()`); todo o desenho (`App.add_char`,
`App._draw_control_panel`) escreve num `core.screen.Screen`, que emite ANSI
bruto direto pro terminal.

- `App.truecolor` é detectado uma vez (`color.supports_truecolor()`, a
  partir de `COLORTERM`) e usado em `Screen.flush()` pra decidir entre
  `\x1b[38;2;r;g;bm` (true color) e `\x1b[38;5;{índice}m` (fallback,
  índice do 256-color mais próximo via `color.nearest_256`).
- `App.get_color(brightness, column_x)` resolve um nível de brilho (0 a
  `NUM_SHADES-1`) numa cor `(rgb, bold)`, interpolando continuamente entre
  os 8 pontos de `palette.theme_gradient_stops()` do tema ativo — em vez de
  indexar direto numa tabela fixa de 8 cores como antes.
- `Screen` reposiciona o cursor explicitamente antes de cada caractere (em
  vez de confiar no avanço automático do terminal) e nunca escreve no
  canto inferior-direito — duas lições vindas do protótipo de fundo/
  profundidade (issue #1): caracteres Katakana de largura completa
  desalinham a linha se o cursor só avança sozinho, e escrever a última
  célula da última linha aciona auto-scroll na maioria dos terminais.

## Como executar e validar

Use Python 3.6 ou superior em um terminal UTF-8. A animação requer um TTY
real; ela deliberadamente falha quando a saída é redirecionada.

```bash
# validação estática mínima
python3 -m py_compile matrix-rain core/*.py modes/*.py

# testes de unidade (só lógica pura — color.py e palette.py, sem curses)
python3 -m unittest discover -s tests -t .

# validação da interface de linha de comando (não precisa de TTY)
./matrix-rain --help

# execução interativa manual
./matrix-rain -c green -s 5 -d 7

# forçar o caminho de fallback (256 cores) mesmo num terminal truecolor
COLORTERM= ./matrix-rain -c green -s 5 -d 7
```

`tests/` cobre `core/color.py` e `core/palette.py` (motor de cor: detecção de
`COLORTERM`, gradiente, conversão de/para 256 cores) e, quando a issue #6
(presets) for implementada, o parsing/merge de TOML — o resto continua
exigindo validação manual porque depende de `curses`/do terminal de verdade.
Depois de alterar a renderização ou a interação, faça ao menos uma
verificação manual em um terminal 256 cores:

- confirme que `q`, `Esc` e `Ctrl+C` restauram o terminal;
- redimensione a janela durante a animação;
- teste um tema comum e `--rainbow`, em ambos os caminhos de cor (truecolor
  e `COLORTERM=` forçando fallback);
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
  a cabeça branca (sempre `(255, 255, 255)` depois de convertido — é o que
  `tests/test_palette.py` verifica). `theme_gradient_stops()` é a única
  ponte entre essa tabela e o motor de cor contínuo; não hard-code RGB de
  tema em outro lugar.
- Mantenha `width - 1` ao criar colunas em `RainMode`. É uma proteção
  intencional para caracteres Katakana de largura ambígua e bordas de
  tela.
- `Screen` (não mais `curses`) é quem decide o que é seguro escrever — não
  duplique a checagem de limites (`0 <= y < height`) em outro lugar; passe
  por `App.add_char`.
- O caminho de saída deve continuar restaurando cursor e atributos ANSI no
  bloco `finally` de `core.cli.run()`.
- `density` controla a quantidade de fluxos ativos em `RainMode` e também o
  atraso de reaparecimento; `speed` controla a velocidade-base de cada
  coluna, que recebe variação aleatória.
- Fora do modo protetor de tela, `W`/`S` e `A`/`D` (ou as setas, `+`/`-` e
  `[`/`]`) ajustam velocidade e densidade; `t` alterna temas, `r` alterna
  arco-íris, `m` alterna os visualizadores e `h` mostra o painel. `p` alterna
  sua visibilidade.
- Um modo nunca chama `curses` diretamente nem acessa `app.stdscr` — passe
  sempre por `app.add_char()`/`app.get_color()`/`app.get_contrast_color()`.

## Alterações comuns

- **Novo tema:** acrescente 8 cores a `COLOR_PALETTE` (`core/palette.py`),
  exponha-o nas escolhas da CLI (isso já acontece automaticamente via
  `core.cli.parse_args()`) e atualize o README. Inclua-o em
  `RAINBOW_SEQUENCE` somente se ele fizer sentido no ciclo arco-íris. Não
  precisa mexer em `core/color.py` — `theme_gradient_stops()` deriva o
  gradiente automaticamente das 8 novas entradas.
- **Ajuste de estética do Rain:** prefira alterar `RainMode._random_speed`,
  `_random_trail_length`, `_update_column` ou `_respawn_column`; não misture
  estado de animação com `_draw`.
- **Novo visualizador:** crie um arquivo em `modes/`, implemente uma classe
  que estenda `modes.base.Mode` (`reset(app)`, `render(app)`), e registre-a
  em `MODE_CLASSES`/`MODE_ORDER` (`modes/__init__.py`). Reuse
  `app.base_speed`, `app.density` e `app.get_color()` para manter os
  controles consistentes com os outros modos.
- **Novo argumento:** implemente-o em `core.cli.parse_args()`, passe-o por
  `core.cli._main()` a `App`, e documente-o no README.
- **Mexeu em `core/color.py` ou `core/palette.py`:** rode
  `python3 -m unittest discover -s tests -t .` antes de validar
  manualmente — é rápido e pega regressão de gradiente/fallback sem
  precisar abrir um terminal.

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
