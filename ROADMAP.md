# Roadmap do NEOMapper

## 4.1.9 — Fundação padronizada

- [x] Repositório canônico separado dos pacotes Runtime.
- [x] Empacotamento moderno com `pyproject.toml`.
- [x] Entry point `python -m neomapper`.
- [x] Separação inicial entre domínio, aplicação, infraestrutura e apresentação.
- [x] Dados de execução fora do código instalado.
- [x] Testes determinísticos para fallback, caminhos, utilitários e domínio.
- [x] Requisitos, arquitetura e regras permanentes documentados.

## 4.1.10 — Candidata pública

- [x] Operações longas executadas fora da thread gráfica.
- [x] Licença do código e avisos de terceiros documentados.
- [x] Empacotamento Python e aplicação Windows reproduzíveis.
- [x] CI para todas as versões de Python suportadas.
- [x] Configuração atômica, caminhos sanitizados e regressões cobertas.

## 4.2.0 — Modularização da interface

- [x] Visualizar relatório de efemérides na tela antes de salvar ou imprimir.
- [x] Exibir AR em h/m/s e Dec em graus/minutos/segundos no relatório, com regressão de arredondamento.

- [x] Adicionar gráfico de altitude em módulo separado e avanço Info Obs. → Camadas.
- [x] Faixas contínuas de crepúsculo, curva lunar opcional e controles do quadro em Camadas.

- [ ] Extrair cabeçalho, configuração, observação, animação e resumo para views.
- [ ] Executar consultas e renderizações longas fora da thread da interface.
- [ ] Cobrir navegação, traduções e estados de erro com testes Qt.
- [ ] Centralizar mensagens visíveis nos catálogos de tradução.

## 4.3.0 — Reprodutibilidade científica

- [ ] Criar fixtures de efemérides versionadas.
- [ ] Adicionar testes de regressão de altitude, azimute e janelas observacionais.
- [ ] Registrar parâmetros e provedor junto aos produtos exportados.
- [ ] Definir tolerâncias numéricas por cálculo.

## 4.4.0 — Distribuição

- [x] Automatizar criação do Runtime a partir do repositório canônico.
- [ ] Validar instalação limpa no Windows sem ambiente Python.
- [x] Gerar pacotes e checksums dos artefatos de distribuição.
- [x] Publicar procedimento de atualização e rollback.

## Ajustes de visualização

- [x] Corrigir órbita inclinada/retrógrada e semieixo do Halley; resolver
  aparições do Horizons e buscar eventos da próxima passagem em períodos longos,
  com regressões científicas e indicação da janela pesquisada.

- [x] Favoritos persistentes com notas, exportação do resumo orbital em PDF/CSV,
  ajuda contextual EN/PT/ES e oferecimento SONEAR/AstroNEOS na aba Sobre.

- [x] Revisar EN/PT/ES nos cards, mensagens, opções de animação e nomes dos
  planetas; validar cobertura dos catálogos e troca de idioma com testes Qt.

- [x] Botão próprio do resumo orbital disponível sem gráfico de altitude;
  cálculo no painel ao clicar, expansão separada e distâncias seguindo Settings.

- [x] Sincronizar noite, critérios e amostras do gráfico de altitude e painel observacional.

- [x] Resumo orbital abaixo do gráfico na área central de projeção, com controle lunar junto ao gráfico e PA antissolar apenas para cometas.

- [x] Mover UTC/LOCAL para Settings e aplicar a preferência aos títulos das animações.

- [x] Reduzir símbolo lunar, sincronizar padrão de animação de 24h e traduzir passos de semana/mês/ano.

- [x] Agrupar imagens e animações por designação e data local de geração.
- [x] Exibir a fase lunar e a orientação do limbo iluminado no mapa celeste.
- [x] Configurar limites independentes de quadros e linhas de efemérides (500 por padrão).

- [x] Preferência persistente UA/km para distâncias astronômicas em cartões,
  mapas, Sistema Solar e animações.
