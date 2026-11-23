# Artefatos da análise da fila da catraca do RU

Arquivos gerados durante a análise das coletas de 16/11 e 17/11/2026.

Relatório completo (documento online): https://claude.ai/artifact/VCudahTDwgqij9SWkzFgmx

## dados/
| Arquivo | Conteúdo |
| --- | --- |
| `registros_observadorA_2026-11-17.csv` | Registros do observador A (fila) em 17/11: 556 chegadas, 43 desistências |
| `coleta_almoco_2026-11-17.csv` | Observadores A e B de 17/11 juntos, em ordem cronológica, com a sessão corrigida para `2026-11-17-almoco` (1.617 registros) |
| `coletas_2026-11-16_todas.csv` | As 3 coletas de 16/11 (PDFs convertidos + TXTs do observador C) |
| `coletas_almoco_16e17-11.csv` | Os dois dias juntos no formato do app, com a coluna `arquivo_origem` (2.393 registros) |
| `coleta_almoco_2026-11-17_fila42.csv` | Igual a `coleta_almoco_2026-11-17.csv`, mas com a fila inicial 42 usada pela equipe (o app gravou 0). Base da análise revisada |
| `coletas_2026-11-16_por_coleta.csv` | `coletas_2026-11-16_todas.csv` no formato do script, uma sessão por coleta (`2026-11-16-coleta1` a `3`), com a fila inicial de cada uma (0, 28 e 0). Início (B) e saída (C) foram anotados em celulares diferentes: os tempos de atendimento são descartados e μ sai das contagens por minuto |

## analise_revisada/ (resultado principal, depois da avaliação do simulador)
17/11 (fila inicial 42) e as três coletas de 16/11, com μ estimado pelas saídas por minuto nos minutos com fila,
modelo M/M/1 (chegadas uma a uma), pico pela regra do slide 59 (1,5 × a média), picos de pelo menos 5 min, K = 200 e os 48 alunos que sobravam no balanço de 17/11 tratados
como saídas que o observador B não registrou (espalhadas depois das 12:16).
`python analise_catraca.py artefatos/dados/coleta_almoco_2026-11-17_fila42.csv artefatos/dados/coletas_2026-11-16_por_coleta.csv --ajuste saidas --reps 500 --comparar-ajustes --saida artefatos/analise_revisada`
Resultado em 17/11 (μ = 6,22 /min, das duas datas): W de 1,9 min (1 catraca) para 1,1 min (2ª catraca das 11:55 às 12:03 e das 12:25 às 12:30, 13 min de catraca extra).
Com μ entre 5,65 e 8,67, W vai de 0,8–2,6 min para 0,5–1,5 min. Curva (89% dos minutos na faixa), trace e μ da 1ª metade validado na 2ª passam;
a fração com fila ≥ 10 fica no limite (59% contra 22%–58%) e o D falha no M/M/1.
Com a regra anterior (duas médias, 44 min de pico): W de 2,8 para 0,7 min e os 3 itens da fila passam (seção REFINAMENTO do relatório).
Pergunta da equipe: a 2ª catraca pela fila (abre com 25 alunos, fecha com 12) fica 7 min aberta e poupa 64 min de espera por
minuto aberta, contra 34 no horário de pico (13 min aberta), com o mesmo W (1,1 min). Com chegadas em grupo a resposta se mantém.
Refinamento (seção REFINAMENTO do relatório): com chegadas em grupo (E[k] = 1,84) o D também passa e W fica 3,0 → 0,9 min.
As pastas abaixo ficam como histórico e usam o modelo anterior (μ fixo, chegadas uma a uma, K = 80).

## analise_original/
Saída do `analise_catraca.py` sem nenhum ajuste, com `coleta_almoco_2026-11-17.csv`.
A validação falha nos 3 itens (μ cronometrado otimista, fila inicial 0, K = 50).

## analise_primeira_hora/
17/11, das 11:31 às 12:31, só com dados observados. Fila inicial 42.
`python analise_catraca.py c17_1h_semcron.csv --mu 6.18 --K 80 --reps 500`
Resultado: W de 3,4 min (1 catraca) para 1,2 min (2ª catraca no pico). Validação passa.

## analise_almoco_inteiro/ (resultado principal)
17/11, das 11:31 às 13:15. Fila inicial 42 e 48 desistências não vistas acrescentadas entre 12:31 e 13:15.
`python analise_catraca.py c17_full_desist.csv --mu 4.94 --K 80 --reps 500`
Resultado: W de 4,1 min (1 catraca) para 1,1 min (2ª catraca no pico). Validação passa.

Nos arquivos `c17_*.csv` os registros `inicio_atend` foram retirados de propósito:
com eles, o script ignora o `--mu` e usa o tempo cronometrado.
