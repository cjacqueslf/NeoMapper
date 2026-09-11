# Validação 4.1.10

## Verificações automatizadas

- Executar a suíte padrão em Python 3.11, 3.12, 3.13 e 3.14 no Windows.
- Confirmar que consultas e renderizações não executam na thread Qt.
- Validar fallback JPL/MPC, janelas contínuas e persistência atômica.
- Construir `sdist` e `wheel` e executar `twine check`.
- Construir o aplicativo PyInstaller e confirmar que `NEOMapper.exe` abre uma
  janela responsiva com o título `NEOMapper - GUI`.
- Gerar instalador, pacote portátil e arquivo `SHA256SUMS.txt`.
- Instalar silenciosamente a candidata, abrir a cópia instalada e desinstalar
  sem deixar o diretório da aplicação.

## Aceitação manual obrigatória

- Instalar e desinstalar em uma conta Windows sem ambiente Python.
- Gerar mapa de visibilidade e carta do céu para `(99942) Apophis`.
- Gerar GIF e MP4 curtos; cancelar uma animação durante a renderização.
- Alternar entre inglês, português brasileiro e espanhol.
- Confirmar procedência JPL/MPC e o crédito ESA na tela Sobre.
- Confirmar que configuração, logs e saídas ficam em `%LOCALAPPDATA%\NEOMapper`.
- Conferir o SHA-256 dos artefatos antes de anexá-los à Release.
