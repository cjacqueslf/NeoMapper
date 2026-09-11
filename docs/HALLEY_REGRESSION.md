# Halley: órbita e eventos de longo período

Correção de 2026-09-10. A distância heliocêntrica instantânea do Halley é maior
que seu semieixo maior nesta época. Usar `max(r, a)` alterava indevidamente a
elipse; desenhá-la apenas com Ω+ω também descartava a inclinação retrógrada.

O provedor de infraestrutura consulta vetores geométricos heliocêntricos em
eclíptica J2000, com época TDB. A aplicação deriva a elipse osculadora do mesmo
estado posição/velocidade usado pelo marcador, usando GM solar do Astropy.
A apresentação projeta ambos em XY. É uma órbita osculadora instantânea, não
uma integração numérica das passagens futuras. A consulta ocorre no worker
responsivo já usado pela interface.

O SPK-ID do Halley é ambíguo no Horizons devido às várias aparições históricas.
Usamos a designação SBDB com `CAP<JD TDB` para escolher a aparição anterior
mais próxima da época solicitada. Esse identificador permanece fixo durante
a busca de eventos, evitando misturar soluções entre lotes.

A janela padrão continua ±365 dias da data selecionada. Se Tp estiver fora
dela e houver período finito de órbita ligada maior que 730 dias, avançamos
Tp por períodos inteiros até a próxima passagem e pesquisamos sua vizinhança
de ±365 dias, excluindo datas anteriores à selecionada. O período osculador
serve somente como estimativa inicial. As distâncias geocêntricas e solares
da tabela de observador Horizons são amostradas diariamente; mínimos locais
e bordas são refinados até resolução de um minuto. Um mínimo solar na borda
não confirma periélio: nesse caso o relatório identifica Tp como estimado.

A menor distância à Terra vale apenas para o intervalo exibido. Não se afirma
que seja a menor distância ao longo de toda a órbita. A grade diária pode
perder encontros muito breves, e uma janela de dois anos pode não conter um
retorno muito perturbado. Efemérides indisponíveis geram erro registrado;
não se substituem por propagação kepleriana não validada. A resolução de busca
de um minuto não representa precisão física da previsão; datas futuras UTC
dependem de segundos intercalares ainda desconhecidos.

Regressão fixa: `tests/fixtures/halley_2026.json`, vetores e elementos do Horizons
em 2026-09-10 UTC. Semieixo ≈17,859443 UA, excentricidade ≈0,9680233,
inclinação ≈162,1884°. Testes verificam semieixo, plano orbital, sentido
retrógrado, coincidência marcador/curva, escala TDB e identidade dos lotes.
Testes sintéticos cobrem Tp passado, próximo retorno, mínimos distintos
Sol/Terra, janela padrão e periélio não confirmado.

Consulta real validada: para 1P em 2026-09-10, janela 2060-08-04 a 2062-08-04,
periélio refinado 2061-07-28 e menor distância terrestre 2061-07-29,
aproximadamente 0,477411 UA. Valores dependem da solução vigente do provedor.

Referências primárias:
- [Horizons: seleção de cometas, escalas e tabelas](https://ssd.jpl.nasa.gov/horizons/manual.html)
- [SBDB: designação e classificação de objetos](https://ssd-api.jpl.nasa.gov/doc/sbdb.html)
