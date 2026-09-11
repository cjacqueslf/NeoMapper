# Publicação de uma versão

Este procedimento produz a distribuição Windows pública e permite voltar à
versão anterior sem substituir arquivos já publicados.

## Preparação

1. Confirme que `APP_VERSION`, o instalador, o README e o changelog usam a
   mesma versão.
2. Execute `python -m pytest -q` e `scripts\build_release.ps1` em Windows x64.
3. Confira o instalador, o ZIP portátil, o pacote Python, o manual e
   `SHA256SUMS.txt` em `dist`.
4. Faça a aceitação manual descrita no documento de validação da versão.
5. Faça commit e merge na branch principal antes de criar a tag.

## Publicação

Crie uma tag anotada que corresponda exatamente à versão do aplicativo:

```powershell
git tag -a v4.2.0 -m "NEOMapper 4.2.0"
git push origin master --follow-tags
```

O workflow `Release` reconstrói tudo em um runner limpo, valida o runtime e
cria a GitHub Release. Um sufixo como `-rc1` cria um pré-lançamento. Baixe os
arquivos publicados e confira `SHA256SUMS.txt` antes de anunciar a versão.

## Atualização e rollback

O instalador atualiza a instalação que usa o mesmo AppId. Configurações e
saídas permanecem em `%LOCALAPPDATA%\NEOMapper`. Para rollback, não mova uma
tag já publicada: marque a release problemática como pré-lançamento, informe o
motivo, mantenha os artefatos para rastreabilidade e indique a última release
estável. Publique a correção com um novo número de versão.

As tags e Releases são imutáveis do ponto de vista do processo. Se um artefato
estiver incorreto, publique outra versão em vez de substituir o arquivo.
