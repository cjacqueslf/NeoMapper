# Requisitos do NEOMapper

## 1. Produto

O NEOMapper auxilia astrônomos amadores e profissionais a planejar observações
de objetos próximos da Terra por meio de mapas de visibilidade, cartas do céu e
animações temporais.

## 2. Requisitos funcionais

### RF-01 — Consulta de efemérides

- Aceitar designação ou número de objeto.
- Consultar o JPL Horizons como provedor principal.
- Consultar o MPES do Minor Planet Center quando o provedor principal falhar.
- Informar qual provedor produziu o resultado.

### RF-02 — Referência geográfica e temporal

- Aceitar latitude, longitude e altitude do observador.
- Aceitar entrada em UTC ou horário local.
- Selecionar UTC/LOCAL nos Settings, com persistência imediata. Títulos e
  rótulos das animações seguem essa seleção, inclusive na mudança de dia.
- Converter cálculos internamente para UTC.
- Permitir limite configurável de altitude solar.

### RF-03 — Produtos visuais

- Gerar mapa global de visibilidade.
- Gerar carta do céu para o local de referência.
- Representar a Lua com a fase do instante selecionado e o lado iluminado
  orientado para o Sol, inclusive a cada quadro de animação.
- Exibir posição do objeto e informações observacionais relevantes.
- Salvar imagens em PNG.
- Agrupar imagens, gráficos e animações em `output/<designação>-<AAAAMMDD>`,
  usando a data local de geração e uma designação segura para nomes no Windows.
- Na aba Info Obs., gerar gráfico de altitude do objeto ao longo de 24 horas,
  com crepúsculos e horários UTC ou locais; permitir continuar para Camadas.
  Usar o mesmo instante selecionado em Camadas e a altura do observador.
  Calcular a janela e o melhor horário com os limites configurados, em amostras
  de 5 minutos compartilhadas pelo gráfico e pelo painel lateral. Restaurar
  esses resultados junto ao gráfico ao retornar à aba, sem valores antigos.
- Abaixo do gráfico de altitude, na área central de projeção (não no painel
  lateral), exibir um resumo de periélio, data
  selecionada e maior aproximação à Terra. Exibir magnitude (V ou T), distâncias
  ao Sol/Terra na unidade de Settings, AR/Dec sexagesimais, elongação e ângulo de fase. Oferecer
  visualização ampliada e esconder PA antissolar para asteroides; classificar
  cometas pelo campo `kind` do SBDB. O resumo é geocêntrico, com datas exibidas
  conforme Settings. Buscar aproximação em ±365 dias, com grade diária e
  refinamento dos mínimos até 1 minuto; indicar período e natureza amostrada.
  O periélio normalmente é Tp osculante na época selecionada, em TDB convertido
  por Astropy. Para órbitas ligadas com período superior a 730 dias e Tp fora
  da janela usual, usar o período para localizar a próxima passagem e consultar
  ±365 dias ao redor dela, somente no futuro. Refinar também a distância ao Sol;
  identificar periélio não confirmado como estimativa. Explicitar que a menor
  distância à Terra vale para a janela pesquisada, não para toda a órbita.
  Falha do resumo não deve impedir o uso do gráfico de altitude.
  O botão próprio de resumo orbital fica azul e disponível independentemente
  do gráfico de altitude; apenas durante sua consulta fica temporariamente
  desabilitado para evitar cliques duplicados. O clique calcula e mostra o
  resumo no painel, usando o objeto, instante e Settings atuais. Somente o
  botão Ampliar resumo abre a janela expandida. As distâncias seguem Settings.
  O controle de mostrar/ocultar Lua fica na parte inferior da própria área de
  projeção, entre o gráfico e o resumo, e acompanha apenas esse gráfico.
  O resumo também pode ser mostrado sozinho na aba de informações observacionais.
- Permitir mostrar/ocultar a curva de altitude lunar no gráfico, em branco suave.
- Configurar a exibição e a posição do quadro observacional na aba Camadas.
- Exportar efemérides na aba Camadas para PDF e selecionar impressora.
  Oferecer “Ver relatório” como ação principal, com visualização de todas as
  páginas e opções de salvar ou imprimir sem repetir a consulta.
  Exibir AR em horas, minutos e segundos e Dec com sinal em graus, minutos e
  segundos; segundos com duas casas decimais, inclusive na prévia e impressão.
  Datas do relatório em UTC; coordenadas e taxas nativas do JPL Horizons para
  latitude/longitude configuradas, elevação de 0 m, sem refração. Movimento em
  arcseg/min e PA do norte para leste; magnitude V ou total cometária T identificada.

### RF-04 — Animação

- Iniciar com a primeira data informada e fim 24 horas depois; atualizar esses
  padrões quando a primeira data mudar. O passo inicial é 5 minutos.
- Oferecer passos de semana, mês e ano com tradução. Mês/ano seguem o calendário
  na escala de entrada escolhida (UTC ou hora local), ajustando dias inexistentes
  ao fim do mês sem desvio acumulado e incluindo o instante final selecionado.

- Gerar quadros em intervalo configurável.
- Exportar GIF e, quando disponível, MP4.
- Permitir cancelamento e apresentar progresso.
- Limitar a quantidade de quadros antes de renderizar, incluindo o quadro final.
  Recusar intervalos acima do limite, sem truncar a animação silenciosamente.

### RF-05 — Internacionalização

- Oferecer interface em inglês, português brasileiro e espanhol.
- Aplicar formatação numérica coerente com o idioma.
- Oferecer EN/PT/ES nos cards, ajuda, status, erros e opções de animação;
  trocar os nomes dos planetas e título do Sistema Solar ao mudar de idioma,
  sem repetir as consultas astronômicas. Validar a cobertura dos catálogos e
  preservar os valores de configuração ao traduzir opções.

### RF-06 — Configuração

- Persistir preferências no diretório de dados do usuário.
- Oferecer campos independentes para limite de quadros e limite de linhas de
  efemérides, ambos com padrão 500. Persistir alterações imediatamente e
  informar o excesso antes de consultar/renderizar; conferir também as linhas
  efetivamente retornadas pelo provedor.
- Nunca gravar configurações ou saídas dentro do pacote instalado.

### RF-07 — Favoritos

- Na aba Objeto, permitir salvar favoritos com designação, nome e notas,
  selecionar e remover entradas. Salvar novamente uma designação atualiza
  o favorito, sem duplicar por diferenças entre maiúsculas e minúsculas.
- A seleção preenche o objeto sem iniciar consulta. Guardar os favoritos
  atomicamente no diretório de dados do usuário e preservar o arquivo em caso
  de erro de leitura ou gravação.

### RF-08 — Exportação do resumo e ajuda

- Exportar o resumo já calculado em PDF ou CSV UTF-8 com separador ponto e
  vírgula, preservando unidades, idioma, instantes completos e convenções.
  Não repetir consultas. Incluir versão do programa e procedência dos dados.
- Oferecer explicações contextuais nos controles e colunas científicas, com
  glossário acessível pelo resumo e pela aba Sobre, em EN/PT/ES.
- Na aba Sobre, informar o oferecimento do Observatório SONEAR e do canal
  AstroNEOS, com convite à inscrição e link para https://www.youtube.com/@AstroNEOS.

## 3. Requisitos não funcionais

- Compatibilidade com Python 3.11 e 3.12 no Windows. A linha estável atual de
  `pyproj`/PROJ usada pelo aplicativo ainda não fornece wheels Windows para
  Python 3.13 ou superior.
- Falhas de rede não podem corromper configurações nem saídas existentes.
- O domínio científico não deve depender de PySide6, rede ou sistema de
  arquivos.
- Consultas externas devem possuir timeout.
- A suíte padrão deve ser determinística e não depender da internet.

## 4. Critérios de qualidade científica

- Instantes devem declarar a escala temporal.
- Distâncias e ângulos devem ter unidades explícitas no contrato ou no nome.
- Mudanças nos cálculos exigem testes com valores de referência.
- A procedência das efemérides deve acompanhar o resultado.

## 5. Fora do escopo atual

- Banco local de efemérides.
- Conta de usuário ou sincronização em nuvem.
- Controle direto de telescópios.
- Serviço web ou publicação pelo Sites.

## Preferência de distância

- Selecionar UA ou km em Ajustes e persistir a escolha entre execuções.
- Aplicar a unidade às distâncias astronômicas nos cartões, mapas, Sistema Solar
  e quadros de animação, com números formatados no idioma selecionado.
- Atualizar cartões e gráficos estáticos ao trocar a unidade, sem nova consulta
  de efemérides. Animações existentes devem ser regeneradas.

## Instante do mapa

- Camadas do Mapa apresenta Data e Hora antes do Tipo de mapa, com modo UTC/LOCAL.
- Gerar Mapa combina o objeto selecionado com esse instante para ambos os tipos.
- A data de Objeto preenche os campos inicialmente; ajustes em Camadas não
  alteram a data da pesquisa do objeto.
