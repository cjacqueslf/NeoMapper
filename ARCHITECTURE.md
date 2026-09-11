# Arquitetura do NEOMapper

## Visão geral

O NEOMapper é uma aplicação desktop modular. O entry point
`neomapper.bootstrap` compõe a interface e os serviços.

```text
presentation  ─────┐
                   ├──> application ──> domain
infrastructure ────┘
```

O domínio não depende das demais camadas.

## Pacotes

- `domain`: cálculos astronômicos e regras observacionais puras.
- `application`: contratos de efemérides, fallback e casos de uso.
- `infrastructure`: provedores externos, arquivos e caminhos de execução.
- `presentation`: PySide6, gráficos, mapas, animações e tradução.
- `presentation.locales`: catálogos EN/PT/ES com as mesmas chaves e campos de
  interpolação. A interface não depende mais de um dicionário português
  complementar. O Sistema Solar mantém os dados do título e identifica os
  rótulos para mudar de idioma sem consultar o provedor ou recalcular órbitas.
- `shared`: versão e utilitários pequenos sem política de aplicação.

## Recursos de uso público

- `application.favorites` define os dados e o contrato de persistência;
  `infrastructure.favorites` grava JSON atomicamente no diretório do usuário.
  `presentation.favorites` gerencia a lista sem consultar efemérides.
- `presentation.summary_export` recebe uma tabela já formatada, independente
  de Qt, e produz PDF/CSV sem recalcular os valores. O widget fornece a data
  completa e as convenções junto às unidades exibidas. Escritas usam arquivo
  temporário antes da substituição do destino.
- `presentation.context_help` compartilha os tópicos entre dicas e glossário;
  textos e créditos ficam nos catálogos EN/PT/ES.

## Fluxo de consulta

1. A apresentação solicita efemérides à aplicação.
2. A aplicação consulta o JPL Horizons.
3. Em falha operacional, a aplicação consulta o adaptador MPC.
4. Ambos os resultados são convertidos para o contrato `Ephemeris`.
5. O domínio calcula visibilidade e janela observacional.
6. A apresentação renderiza e salva o produto.

## Dados de execução

`presentation.report_preview` exibe o PDF de efemérides com `QPdfView`.
`presentation.coordinates` formata AR/Dec sexagesimais somente na apresentação,
preservando os valores em graus do provedor. AR é normalizada em [0, 24h),
inclusive após arredondamento; Dec mantém o sinal, inclusive próximo de zero.
O arredondamento a 0,01 segundo propaga o transporte entre segundos e minutos.
A consulta e a geração da prévia executam em worker. O PDF temporário fica
no diretório de saídas do usuário e é removido ao fechar a prévia; salvar
copia esse mesmo documento e imprimir reutiliza a seleção nativa de impressora.

O código e os recursos somente leitura ficam no pacote. Configuração, logs e
saídas são gravados em `%LOCALAPPDATA%\NEOMapper`, ou no caminho definido por
`NEOMAPPER_DATA_DIR`.

## Decisões

- O gráfico de altitude usa o instante de Camadas, evitando comparar uma noite
  escolhida à meia-noite com a noite do mapa escolhido à tarde. O resultado
  `AltitudeChartResult` transporta o PNG e a janela observacional calculada das
  mesmas amostras de 5 minutos por `domain.observing.observing_window_from_samples`.
  O máximo anotado respeita altitude mínima e limite solar, e o painel é
  atualizado/restaurado desses dados. Os cálculos da janela nos mapas também
  recebem a altura do observador, antes implicitamente zero. Regressão de rede
  separada reproduz 2026 RW3 em 2026-09-09 18:42 LOCAL, Belo Horizonte: melhor
  horário aproximadamente 21:25 LOCAL, altitude 89,7 graus.

- A área central separa a imagem (`plot_area`) dos detalhes de altitude
  (`altitude_details`): controle lunar e resumo ficam abaixo do gráfico na
  projeção. A limpeza de imagens preserva esses widgets, e a navegação só os
  exibe ao restaurar uma imagem do gráfico de altitude.

- O resumo orbital usa `application.object_summary.SummaryProvider`, implementado
  por `infrastructure.ephemeris.summary.HorizonsSummaryProvider`: SBDB identifica
  `cn/cu` como cometas e `an/au` como asteroides, sem heurísticas de nome. Asteroides
  usam SPK-ID; cometas usam `DES=designação;CAP<época TDB;` para selecionar a
  aparição anterior mais próxima da época solicitada. O mesmo comando é
  preservado em todos os lotes, inclusive futuros. Elementos
  heliocêntricos recebem épocas TDB, e Tp é interpretado em TDB; efemérides
  geocêntricas recebem épocas UTC. Lotes limitados a 50 épocas para evitar
  URLs longas rejeitadas pelo serviço, timeout 20s.
  Não há fallback científico para estas grandezas; indisponibilidade é informada
  no painel e detalhada em log, mantendo o gráfico já gerado.
- A aproximação do resumo é o menor delta amostrado em ±365 dias. Para períodos
  longos com Tp fora dessa janela, pesquisa-se a vizinhança da próxima passagem,
  conforme [a justificativa científica](docs/HALLEY_REGRESSION.md). Refinam-se
  todos os mínimos locais da grade diária e os limites do intervalo, primeiro
  com 49 amostras e depois 121 amostras na vizinhança do mínimo (até 1 minuto).
  Isto não garante detectar eventos menores que a grade diária nem prevê o
  mínimo de toda a órbita. O quadro explicita intervalo e aproximação. Testes
  sintéticos cobrem múltiplos mínimos; o teste de rede separado verifica 220P
  na data 2026-09-09. PA usa `sunTargetPA` (PsAng), orientação antissolar da cauda
  de gás, do norte para leste, e só aparece em cometas. Fontes:
  https://ssd-api.jpl.nasa.gov/doc/sbdb.html e
  https://ssd.jpl.nasa.gov/horizons/manual.html#observer-table

- Os renderizadores separam `time_mode` (interpretação da entrada) de
  `display_time_mode` (títulos e rótulos, por padrão igual à entrada).
  Animações passam instantes UTC e preservam o modo dos Settings para exibição,
  evitando conversão duplicada ou títulos UTC quando o usuário escolheu LOCAL.

- `application.animation_schedule` ancora passos mensais e anuais na primeira
  data civil, preserva anos bissextos e valida a quantidade antes de criar a
  lista. Cada instante é convertido para UTC antes da renderização. A Lua usa
  um símbolo com metade do diâmetro anterior, preservando a geometria da fase.

- `infrastructure.paths.object_output_dir` agrupa produtos pela designação e
  data civil local de geração (`AAAAMMDD`), sem modificar o instante astronômico
  escolhido. Cada execução de animação usa um sufixo de geração para evitar
  reutilização de quadros antigos e colisões com a limpeza do player.
- `application.generation_limits` conta amostras antes da consulta/renderização.
  Relatórios contam a grade regular inclusiva; animações incluem também o fim
  quando não coincide com o passo. O limite padrão 500 vem de `limits` no INI;
  não há corte silencioso nem criação de uma lista ilimitada de instantes.
- `domain.lunar_phase` calcula a fase pela geometria Sol–Lua–observador nas
  posições aparentes topocêntricas e distâncias em UA já fornecidas pelo Astropy
  builtin no instante UTC do mapa. A fração iluminada é `(1 + cos(i))/2`.
  `presentation.lunar_marker` desenha o terminador esférico e orienta o limbo
  brilhante pela tangente em direção ao Sol, projetada na carta. O disco é um
  símbolo ampliado, sem textura, libração ou modelagem de eclipses; os cálculos
  de posição e visibilidade existentes são preservados. Regressões incluem as
  quatro fases principais publicadas pelo USNO (setembro/outubro de 2026), com
  tolerância absoluta de 0,02 na fração para paralaxe topocêntrica e efeméride
  builtin: https://aa.usno.navy.mil/calculated/moon/phases?date=2026-09-01&nump=8
  API de posição aparente: https://docs.astropy.org/en/stable/api/astropy.coordinates.get_body.html

- `Astropy Time` é o tipo temporal científico.
- O JPL continua sendo o provedor principal para preservar o comportamento
  validado.
- O fallback MPC é explícito e testável.
- Dados Hipparcos e catálogos de tradução são recursos empacotados.
- A suíte padrão não acessa a internet.
- `presentation.altitude_plot` renderiza o gráfico observacional em worker,
  reutilizando o cálculo topocêntrico do domínio e a consulta com fallback da
  aplicação. O intervalo vai de meio-dia solar local ao seguinte, com amostras
  a cada cinco minutos; o máximo marcado é amostrado, não um trânsito calculado.
  Os eixos usam UTC ou o fuso civil do local. Não há alteração dos algoritmos
  científicos existentes.
- A curva lunar usa `domain.observing.moon_altitudes_deg`: efeméride builtin do
  Astropy, posição topocêntrica com altitude do observador e sem refração.
  Regressão numérica tolera 0,001 grau para variações dos dados IERS. As versões
  PNG com e sem Lua compartilham a consulta do objeto; alternar é uma operação
  local. As faixas de crepúsculo interpolam linearmente os cruzamentos solares
  em 0, -6, -12 e -18 graus entre amostras, sem intervalos vazios.

## Dívida controlada

`presentation.gui` permanece grande porque uma divisão completa dos widgets
durante a migração aumentaria o risco de regressão visual. A extração em views
menores será feita incrementalmente, protegida por testes de interface.

## Unidades de distância na apresentação

`presentation.distances` centraliza a conversão e formatação de distâncias.
O resumo orbital também usa esse formatador, mantendo os dados científicos em UA.
A consulta do resumo usa os campos atuais da interface, independentemente do
gráfico de altitude, e ocorre em um worker. O resultado aparece no painel;
a expansão tem botão separado. Alterações nos parâmetros invalidam os dados
exibidos sem bloquear novas consultas.
A preferência `ui.distance_unit` (UA ou km; padrão km) é transmitida aos
renderizadores e aos quadros de animação. Os valores numéricos dos contratos
continuam nas unidades explícitas originais. Figuras estáticas retêm os valores
canônicos de suas legendas para mudar de unidade sem novas consultas externas.
