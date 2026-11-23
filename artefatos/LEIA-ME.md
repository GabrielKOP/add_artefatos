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
