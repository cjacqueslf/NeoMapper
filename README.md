# NEOMapper

Aplicação desktop para gerar mapas de visibilidade, cartas do céu e animações
para objetos próximos da Terra. A aplicação consulta primeiro o JPL Horizons e
usa o serviço MPES do Minor Planet Center como contingência.

O código canônico está na versão `4.2.5`. Consulte `REQUIREMENTS.md`,
`ARCHITECTURE.md` e `ROADMAP.md` antes de desenvolver funcionalidades.

## Instalação para usuários

No Windows, baixe `NEOMapper-4.2.5-Windows-x64-Setup.exe` na página da versão
publicada e siga o assistente. O arquivo `NEOMapper-Windows-x64.zip` é a edição
portátil: extraia o conteúdo e execute `NEOMapper.exe`. Configurações, logs e
produtos gerados ficam no diretório de dados do usuário, não na pasta do
programa.

O executável ainda não possui assinatura digital. O Windows pode exibir um
aviso de reputação na primeira execução; confirme sempre que o arquivo veio da
página oficial do projeto e confira o checksum publicado com a versão.

## Ambiente de desenvolvimento

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest
.venv\Scripts\python -m neomapper
```

Para produzir os artefatos de lançamento no Windows:

```powershell
.venv\Scripts\python -m pip install -e ".[dev,release]"
.\scripts\build_release.ps1
```

## Publicação no GitHub

Cada push e pull request executa testes no Windows com Python 3.11 e 3.12. Para
publicar uma versão, atualize a versão e o changelog, faça o merge na branch
principal e crie uma tag anotada com o mesmo número:

```powershell
git tag -a v4.2.5 -m "NEOMapper 4.2.5"
git push origin master --follow-tags
```

A tag dispara o workflow de release. Ele repete os testes, constrói o pacote
Python, o aplicativo portátil, o instalador e o manual, valida o runtime e
publica todos os artefatos com `SHA256SUMS.txt`. Tags com sufixo, como
`v4.2.0-rc1`, são publicadas como pré-lançamento.

Consulte [RELEASING.md](RELEASING.md) para a validação manual e o procedimento
de atualização ou rollback.

Por padrão, configurações, logs e imagens geradas ficam em
`%LOCALAPPDATA%\NEOMapper`. Para desenvolvimento e testes, defina
`NEOMAPPER_DATA_DIR`.

## Limites operacionais

- A aplicação depende de rede para consultar efemérides ainda não armazenadas.
- Resultados astronômicos devem registrar o provedor utilizado.
- A indisponibilidade simultânea do JPL Horizons e do MPC deve ser apresentada
  claramente ao usuário.
- Horários astronômicos são processados em UTC; conversões locais pertencem à
  apresentação.

## Aviso científico

O NEOMapper é uma ferramenta de planejamento e divulgação. Efemérides e mapas
dependem dos dados retornados pelos provedores externos e das hipóteses
documentadas no projeto. Confirme observações críticas em fontes oficiais; o
programa não deve ser usado como único sistema para decisões de segurança ou
operações de defesa planetária.

## Privacidade e rede

Ao consultar um objeto, sua designação, o instante solicitado e parâmetros da
consulta são enviados ao JPL Horizons ou, quando necessário, ao Minor Planet
Center. O NEOMapper não possui conta de usuário nem telemetria própria.

## Licença

O código-fonte é distribuído sob a licença MIT. O subconjunto Hipparcos
empacotado possui licença própria (CC BY-NC 3.0 IGO) e requer **Credit: ESA**.
Consulte `LICENSE` e `THIRD_PARTY_NOTICES.md` antes de redistribuir.
