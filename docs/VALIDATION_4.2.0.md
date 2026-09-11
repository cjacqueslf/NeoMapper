# Validação 4.2.0

## Verificações automatizadas

- Executar a suíte padrão em Python 3.11, 3.12, 3.13 e 3.14 no Windows.
- Construir `sdist` e `wheel` e executar `twine check`.
- Gerar o aplicativo PyInstaller e executar os autotestes de GIF, MP4,
  Cartopy e PROJ no runtime congelado.
- Gerar instalador, pacote portátil, manual e `SHA256SUMS.txt`.
- Confirmar que o ZIP portátil inclui a licença MIT e os avisos de terceiros.
- Confirmar que a tag Git corresponde à versão do aplicativo.
- Confirmar que nenhum ambiente virtual, log, saída ou chave entra no Git.

## Regressões da versão

- Conferir as três linhas do resumo orbital no painel compacto.
- Calcular o resumo do 1P Halley e confirmar a busca da passagem de 2061.
- Conferir que o marcador do Halley coincide com sua órbita inclinada.
- Cadastrar pelo menos dois favoritos em sequência.
- Exportar o resumo em PDF e CSV nas unidades UA e km.
- Alternar inglês, português brasileiro e espanhol em todas as abas.
- Confirmar a mensagem visível durante o cálculo do resumo orbital.

## Aceitação manual antes da publicação

- Instalar e desinstalar em uma conta Windows sem Python instalado.
- Abrir o executável instalado e o portátil em diretórios separados.
- Gerar mapa de visibilidade, mapa celeste, gráfico de altitude e animação curta.
- Confirmar os créditos SONEAR, AstroNEOS e ESA na tela Sobre.
- Confirmar que configuração, favoritos, logs e saídas ficam em
  `%LOCALAPPDATA%\NEOMapper`.
- Comparar todos os artefatos baixados da Release com `SHA256SUMS.txt`.

## Resultado local da candidata

Em 2026-09-10, a suíte padrão passou com 153 testes e 4 testes de rede
excluídos. Os três testes de rede executados separadamente também passaram.
O build 4.2.0 gerou e validou `sdist`, `wheel`, aplicativo portátil, instalador,
manual e cinco hashes SHA-256. Os autotestes de animação e mapa passaram tanto
na árvore congelada quanto numa instalação silenciosa temporária. A
desinstalação silenciosa terminou com código zero.

Os manuais em português, inglês e espanhol foram reconstruídos a partir da
interface 4.2.0, incluindo capturas atuais das seis abas, Favoritos e Resumo
Orbital.

Permanece obrigatória a aceitação em uma máquina ou conta limpa sem Python e a
criação da tag pública.
