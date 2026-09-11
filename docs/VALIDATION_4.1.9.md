# Validação 4.1.9

## Escopo

Migração do código da distribuição Runtime para o repositório canônico,
padronização do empacotamento e separação inicial de camadas.

## Verificações obrigatórias

- Importação de todos os módulos.
- Correspondência entre versão do pacote e aplicação.
- Parser MPC e fallback JPL/MPC.
- Caminhos de configuração, logs e saídas.
- Utilitários de nomes e duração.
- Construção e localização do máximo na grade observacional.
- Inicialização da janela principal em modo sem tela.

## Verificações manuais antes de distribuir

- Gerar mapa de visibilidade para `(99942) Apophis`.
- Gerar carta do céu no local de referência.
- Gerar GIF curto e cancelar uma animação em andamento.
- Alternar entre inglês, português e espanhol.
- Confirmar a procedência JPL ou MPC na interface.
