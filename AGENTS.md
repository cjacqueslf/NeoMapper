# Regras permanentes do NEOMapper

Este arquivo aplica-se a todo o repositório.

## Escopo

- O NEOMapper é uma aplicação desktop astronômica executada no Windows.
- Implementar incrementos pequenos, testáveis e compatíveis com o `ROADMAP.md`.
- Não alterar algoritmos científicos sem teste de regressão e justificativa
  documentada.

## Arquitetura

- Manter dependências apontando de `presentation` e `infrastructure` para
  `application` e `domain`; o domínio não importa Qt, rede ou arquivos.
- Não colocar cálculos astronômicos em widgets ou handlers de clique.
- Encapsular provedores externos na infraestrutura e expor contratos estáveis
  pela aplicação.
- Configurações, logs e saídas pertencem ao diretório de dados do usuário.

## Tempo e unidades

- Usar `astropy.time.Time` para instantes astronômicos e declarar a escala.
- Manter unidades explícitas nos nomes ou por objetos `astropy.units`.
- Longitudes devem ser normalizadas de forma documentada.
- Evitar comparações exatas entre números de ponto flutuante.

## Interface e tradução

- Todo texto visível novo deve passar pelo mecanismo de tradução.
- Operações de rede ou geração de animações não devem bloquear a interface.
- Erros devem ser claros para o usuário e detalhados nos logs.

## Qualidade

- Usar type hints no código novo.
- Regras científicas, conversões de tempo e fallbacks de provedores exigem
  testes unitários.
- Testes de rede devem ser marcados e não integrar a suíte padrão.
- Atualizar requisitos, arquitetura e roadmap quando uma decisão mudar o
  produto.
