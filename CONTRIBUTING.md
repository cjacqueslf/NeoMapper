# Contribuindo com o NEOMapper

O NEOMapper aceita correções e melhorias pequenas, testáveis e coerentes com
o `ROADMAP.md`. Antes de alterar cálculos astronômicos, abra uma issue com a
fonte científica, a escala temporal, as unidades e a tolerância esperada.

Use Python 3.11 ou posterior no Windows:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest
```

Todo texto visível precisa de versões em inglês, português brasileiro e
espanhol. Operações de rede e renderizações não podem bloquear a interface.
Inclua testes unitários para regras científicas, conversões de tempo e
fallbacks de provedores. Marque testes que acessam a rede com `network`.

Ao enviar um pull request, descreva o problema, a mudança observável, os testes
executados e qualquer limite científico. Não inclua ambientes virtuais, dados
de usuário, logs, saídas geradas ou material de assinatura.
