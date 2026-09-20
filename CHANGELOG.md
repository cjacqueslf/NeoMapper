# Histórico de versões

Todas as mudanças relevantes do NEOMapper serão registradas neste arquivo.

## 4.2.5 — 2026-09-20

### Corrigido

- O teste de consistência de versão acompanha a versão publicada, permitindo a
  validação e a geração automatizada dos artefatos de release.

## 4.2.4 — 2026-09-20

### Alterado

- Os nomes de arquivos de animação passam a registrar objeto, local de
  referência, mapa, início e fim, passo temporal, velocidade de reprodução e
  escala de tempo (UTC ou LOCAL), além do identificador de geração.
- Ajuda contextual e geração de manuais usam a versão atual do aplicativo, sem
  referências fixas à versão 4.2.0.

### Corrigido

- A consulta de contingência ao MPC usa o formato de data esperado pelo MPES e
  preserva a mensagem de erro textual devolvida pelo serviço quando não há
  efemérides.

## 4.2.3 — 2026-09-12

### Alterado

- A aba Animação informa em destaque qual mapa será gerado, orienta a troca na
  aba Camadas e esclarece que o Player exige a preservação dos quadros gerados.
  Para Mapa celeste, também informa que o objeto só é plotado acima do horizonte.
- O instalador bloqueia Windows anterior ao 10 e sistemas de 32 bits. Ele alerta
  sobre memória física abaixo de 8 GB, com aviso reforçado abaixo de 4 GB.

## 4.2.2 — 2026-09-11

### Incluído

- Favoritos com designação, nome e notas na aba Objeto, salvos localmente.
- Resumo orbital exportável em PDF e CSV, usando os dados já calculados e
  preservando unidades, idioma, datas completas e convenções.
- Ajuda contextual e glossário nas três línguas. A aba Sobre inclui o
  oferecimento do Observatório SONEAR e do AstroNEOS e o link para inscrição.
- Automação de GitHub Release por tag, com instalador, edição portátil, pacote
  Python, manual e checksums.
- Manual do usuário refeito para o fluxo atual de seis abas, com capturas da
  versão 4.2.0, Favoritos, Resumo Orbital, exportações e ajuda contextual.
- Manuais da versão 4.2.0 também disponíveis em inglês e espanhol, com
  capturas localizadas e incluídos nos artefatos de distribuição.

### Corrigido

- Quadro de efemérides usa como padrão a data e hora selecionadas na aba
  Objeto, em vez da hora do sistema.
- Aba Sobre passa a creditar o desenvolvimento a Cristóvão Jacques em
  colaboração com OpenAI Codex, com quebra de linha para o texto completo.

- Resumo orbital ajusta a altura da tabela às três linhas e às quebras de texto,
  mantendo a maior aproximação visível no painel sem precisar expandir.
- O cálculo do resumo exibe uma mensagem visível abaixo do gráfico.
- Sistema Solar usa o mesmo estado heliocêntrico tridimensional para o marcador
  e a órbita osculadora, preservando inclinação, sentido retrógrado e semieixo.
- Resumo resolve aparições de cometas e pesquisa a próxima passagem em períodos
  longos; identifica janela e estimativas em português, inglês e espanhol.

- Favoritos recebe botão Novo favorito para limpar o formulário e cadastrar
  outros objetos; abrir a janela preserva a designação atual mesmo com uma
  lista já cadastrada.

- Resumo orbital pode ser calculado sem gráfico de altitude e aparece no painel;
  a janela ampliada abre somente pelo botão Ampliar resumo.

- Revisão de espanhol, inglês e português: catálogos completos para os textos
  registrados da interface, cards de Objeto, aba Sobre, mensagens de status e
  erros, reprodução e opções de animação. Rótulos do Sistema Solar acompanham
  a troca de idioma sem recalcular as órbitas; revisão de cabeçalhos de
  efemérides e magnitude no mapa celeste.

- Camadas do Mapa recebe Data e Hora acima do Tipo de mapa, com seleção
  UTC/LOCAL. Gerar Mapa usa esse instante e o objeto selecionado, sem alterar
  a data da pesquisa na aba Objeto.

- Ajustes permite escolher UA ou km, com preferência persistente para cartões,
  mapas de visibilidade/celestes, Sistema Solar e novas animações. A troca atualiza
  cartões e gráficos estáticos sem consultar novamente os provedores; animações
  anteriores precisam ser geradas novamente.

- Sistema Solar desenha órbitas planetárias osculantes a partir do estado
  heliocêntrico na data escolhida, substituindo círculos de raio fixo. Órbitas
  e marcadores usam a mesma projeção eclíptica J2000; aproximação de dois corpos.

- Busca de objeto não encontrado no JPL/MPC apresenta aviso simples no idioma
  escolhido, preservando os detalhes técnicos no log.

- Aba Objeto reúne objeto e data antes de Buscar, com título e legendas da data
  traduzidos para português.

- Animação celeste preserva os horários solicitados ao concluir, sem substituir
  os campos locais pelos horários efetivos dos quadros em UTC.

- Camadas mostra apenas opções do mapa selecionado: controles geográficos no
  Mapa de Visibilidade e magnitude limite das estrelas no Mapa Celeste.
- Botão Continuar para Animação na aba Camadas.

- Fluxo inicial destaca Buscar e habilita Plotar Sistema Solar e Continuar
  apenas após pesquisa bem-sucedida. Botões desabilitados usam cores neutras.
- Mensagens da área de prévia acompanham a aba quando não há gráfico exibido.
- Alterações de objeto ou data invalidam a pesquisa anterior.

- Gerar Mapa exibe a prévia do tipo selecionado; Buscar mantém a orientação
  para gerar o mapa. Magnitude limite das estrelas aparece apenas no Mapa Celeste.
- Botão da curva lunar movido para baixo do gráfico.

- Faixas de crepúsculo contínuas, com bordas interpoladas nos limites solares.
- Curva opcional da Lua em branco suave, alternável no cabeçalho do gráfico.
- Info Obs. sem cartões de horário do mapa e distância; controles de exibição
  e posição do quadro observacional transferidos para Camadas.

- A aba Info Obs. oferece um gráfico de altitude com fundo noturno, faixas de
  crepúsculo, máxima amostrada e marcador do instante atual quando no intervalo.
- Botão para continuar de Info Obs. para Camadas, inclusive após revisitar a aba.
- O gráfico consulta efemérides em segundo plano, usa o local e a data configurados
  e salva PNG no diretório de dados do usuário; textos disponíveis em EN/PT/ES.

## 4.1.10 — 2026-09-07

### Incluído

- Licença MIT, avisos de terceiros e metadados para publicação pública.
- Pipeline de testes para Python 3.11–3.14 e build automatizado no Windows.
- Pacote portátil, instalador Inno Setup e checksums SHA-256.
- Crédito e licença do subconjunto Hipparcos fornecido pela ESA.

### Corrigido

- Consultas, mapas e animações executam fora da thread gráfica.
- Janelas observacionais descontínuas não são apresentadas como um intervalo único.
- A preferência de remoção dos frames temporários é respeitada.
- Configurações são gravadas atomicamente e nomes de saída são sanitizados.
- Alertas científicos do Astropy/ERFA não são ocultados globalmente pelo domínio.
- O aplicativo congelado inclui os dados necessários do Astroquery/PyVO e
  resolve corretamente os runtimes ICU e Microsoft C++ usados pelo Qt.
- O catálogo Hipparcos e os arquivos de tradução são incluídos e verificados
  automaticamente na distribuição Windows.
- Os metadados do `imageio` são incluídos no aplicativo e a geração de GIF/MP4
  é validada automaticamente antes de criar os artefatos de lançamento.
- A projeção geográfica é reutilizada entre os quadros da animação e cada
  figura é liberada após a gravação, evitando falhas nativas no PROJ no Windows.
- O runtime geográfico Windows usa a série estável `pyproj 3.6`/PROJ 9.3 para
  evitar a violação de acesso observada na geração contínua de quadros.

## 4.1.9 — 2026-09-07

### Incluído

- Estrutura modular inicial de domínio, aplicação, infraestrutura e apresentação.
- Mapas de visibilidade, cartas do céu e animações GIF/MP4.
- Consulta principal ao JPL Horizons com fallback para o MPC.
- Interface em inglês, português brasileiro e espanhol.
- Empacotamento Python moderno e automação de testes no Windows.

### Corrigido

- Janelas observacionais descontínuas não são mais apresentadas como um único intervalo.
- A preferência de remoção dos frames temporários de animação é respeitada.
- Salvamento de configuração é atômico para preservar o arquivo anterior em caso de falha.
- Nomes de objetos são sanitizados antes de formar caminhos de saída.
- Alertas científicos do Astropy/ERFA não são mais ocultados globalmente pelo domínio.
