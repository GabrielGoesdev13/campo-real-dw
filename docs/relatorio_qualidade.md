# Relatório de Qualidade de Dados — Campo Real Energia

_Gerado automaticamente por `run_pipeline.py --etapas relatorio` em 12/11/2026 22:17. Fonte: tabelas `qualidade.metrica`, `qualidade.regra`, `qualidade.quarentena` e `qualidade.impacto_limpeza`._
## 1. Resumo

- **47 regras** avaliadas, cobrindo as **7 dimensões** de qualidade.
- **1.996.728 verificações** de registro; **625 falhas** em **25 regras**.
- **6 registros em quarentena** (fora do caminho até o DW, guardados com o JSON original).
- Geração 2025: **3.867.483 MWh antes** × **3.121.704 MWh depois** (-19,28%).
- Receita valorada ao PLD: **R$ 743,47 mi antes** × **R$ 613,41 mi depois** (-17,49%).

## 2. Índice de qualidade por dimensão

Índice = 100% − (registros com falha ÷ registros avaliados). Um mesmo registro pode falhar em mais de uma regra.

| Dimensão | Regras | Avaliados | Falhas | Regras com falha | Índice (%) |
|---|---|---|---|---|---|
| Atualidade | 4 | 78.817 | 294 | 3 | 99,627 |
| Acurácia | 5 | 350.274 | 98 | 3 | 99,972 |
| Completude | 9 | 429.171 | 104 | 4 | 99,976 |
| Integridade referencial | 3 | 157.649 | 25 | 1 | 99,984 |
| Unicidade | 5 | 236.446 | 30 | 3 | 99,987 |
| Consistência | 9 | 394.037 | 41 | 5 | 99,990 |
| Validade | 12 | 350.334 | 33 | 6 | 99,991 |

## 3. Problemas encontrados, decisão e justificativa

Ações possíveis: **CORRIGIR** (valor alterado, original preservado), **DESCARTAR** (cópia removida), **QUARENTENA** (retirado e guardado para auditoria), **SINALIZAR** (mantido e marcado), **COMPLEMENTAR** (dado de referência acrescentado).

### Acurácia


**MED-A01 — Energia mais de 100 vezes maior que a potência instalada (unidade errada, kWh)**  
Tabela: `public.medicao_geracao` · Afetados: **24** de 78.798 (0,030%) · Decisão: **CORRIGIR**  
Justificativa: Lançamento MANUAL vindo de planilha em kWh: dividido por 1.000, o valor volta à faixa normal da usina e fica coerente com as horas vizinhas.
Exemplos: `{"id_usina": 5, "cod_usina": "CRE-BIO-005", "data_hora": "2025-05-10T00:00:00", "id_medicao": 27872, "cod_submercado": "SE"}`; `{"id_usina": 5, "cod_usina": "CRE-BIO-005", "data_hora": "2025-05-10T01:00:00", "id_medicao": 27881, "cod_submercado": "SE"}`; `{"id_usina": 5, "cod_usina": "CRE-BIO-005", "data_hora": "2025-05-10T02:00:00", "id_medicao": 27890, "cod_submercado": "SE"}`

**MED-A02 — Energia acima da potência instalada em 1 hora (fisicamente impossível)**  
Tabela: `public.medicao_geracao` · Afetados: **2** de 78.798 (0,003%) · Decisão: **CORRIGIR**  
Justificativa: Se o valor dividido por 10 bate com as horas vizinhas, é vírgula deslocada e se divide por 10. Se não bate, é pico de leitura e o valor é estimado por interpolação (ESTIMADO).
Exemplos: `{"id_usina": 1, "cod_usina": "CRE-UHE-001", "data_hora": "2025-04-22T14:00:00", "id_medicao": 24104, "cod_submercado": "S"}`; `{"id_usina": 3, "cod_usina": "CRE-EOL-003", "data_hora": "2025-07-03T03:00:00", "id_medicao": 39562, "cod_submercado": "S"}`

**MED-A03 — Valor idêntico por 12 horas ou mais (medidor travado)**  
Tabela: `public.medicao_geracao` · Afetados: **72** de 78.798 (0,091%) · Decisão: **SINALIZAR**  
Justificativa: O valor travado é plausível (próximo do fator de capacidade típico da usina na safra), e não há leitura alternativa para substituir. A medição é mantida e sinalizada para a manutenção do medidor.
Exemplos: `{"id_usina": 5, "cod_usina": "CRE-BIO-005", "data_hora": "2025-09-01T00:00:00", "id_medicao": 52496, "cod_submercado": "SE"}`; `{"id_usina": 5, "cod_usina": "CRE-BIO-005", "data_hora": "2025-09-01T01:00:00", "id_medicao": 52505, "cod_submercado": "SE"}`; `{"id_usina": 5, "cod_usina": "CRE-BIO-005", "data_hora": "2025-09-01T02:00:00", "id_medicao": 52514, "cod_submercado": "SE"}`

### Atualidade


**MED-T01 — Medição recebida mais de 48 h depois da hora medida**  
Tabela: `public.medicao_geracao` · Afetados: **292** de 78.798 (0,371%) · Decisão: **SINALIZAR**  
Justificativa: O dado está correto, mas chegou tarde para o fechamento diário. É mantido e sinalizado para acompanhar o SLA da integração.
Exemplos: `{"id_usina": 8, "cod_usina": "CRE-UHE-008", "data_hora": "2025-12-20T00:00:00", "id_medicao": 76249, "cod_submercado": "N"}`; `{"id_usina": 8, "cod_usina": "CRE-UHE-008", "data_hora": "2025-12-20T01:00:00", "id_medicao": 76258, "cod_submercado": "N"}`; `{"id_usina": 8, "cod_usina": "CRE-UHE-008", "data_hora": "2025-12-20T02:00:00", "id_medicao": 76267, "cod_submercado": "N"}`

**MED-T02 — Usina que parou de enviar dados antes do fim do período**  
Tabela: `public.medicao_geracao` · Afetados: **1** de 9 (11,111%) · Decisão: **SINALIZAR**  
Justificativa: A falta de dados no fim do ano não é geração zero. As horas ficam fora do fato e a usina é apontada para a operação.
Exemplos: `{"id_usina": 4, "data_hora": "2025-12-28T23:00:00"}`

**PLD-T01 — Último mês publicado com mais de 2 meses de atraso em relação a hoje**  
Tabela: `tratado.pld_horario` · Afetados: **1** de 1 (100,000%) · Decisão: **SINALIZAR**  
Justificativa: Mostra se a extração está trazendo o dado mais recente disponível.
Exemplos: `{"ultimo_mes": "2025-12"}`

### Completude


**MED-C01 — Energia gerada nula**  
Tabela: `public.medicao_geracao` · Afetados: **6** de 78.798 (0,008%) · Decisão: **CORRIGIR**  
Justificativa: Falha de comunicação de poucas horas. A energia é estimada por interpolação linear entre a hora anterior e a seguinte (só lacunas de até 6 h), marcada como ESTIMADO, e o valor original (nulo) fica preservado.
Exemplos: `{"id_usina": 8, "cod_usina": "CRE-UHE-008", "data_hora": "2025-03-05T10:00:00", "id_medicao": 13699, "cod_submercado": "N"}`; `{"id_usina": 8, "cod_usina": "CRE-UHE-008", "data_hora": "2025-03-05T11:00:00", "id_medicao": 13708, "cod_submercado": "N"}`; `{"id_usina": 8, "cod_usina": "CRE-UHE-008", "data_hora": "2025-03-05T12:00:00", "id_medicao": 13717, "cod_submercado": "N"}`

**MED-C02 — Horas sem nenhuma medição para a usina no ano (esperado: 8.760 por usina)**  
Tabela: `public.medicao_geracao` · Afetados: **96** de 78.840 (0,122%) · Decisão: **SINALIZAR**  
Justificativa: Não se inventa um dia inteiro de vento ou de sol. As horas faltantes ficam fora do fato e o painel mostra a cobertura; inventar levaria a uma receita que não aconteceu.
Exemplos: `{"id_usina": 3, "data_hora": "2025-11-10T10:00:00"}`; `{"id_usina": 3, "data_hora": "2025-11-10T11:00:00"}`; `{"id_usina": 3, "data_hora": "2025-11-10T12:00:00"}`

**MED-C03 — Disponibilidade (MW) nula**  
Tabela: `public.medicao_geracao` · Afetados: **1** de 78.798 (0,001%) · Decisão: **SINALIZAR**  
Justificativa: A disponibilidade é informativa; a linha afetada é a mesma sem usina (MED-I01).
Exemplos: `{"id_usina": null, "cod_usina": null, "data_hora": "2025-10-20T14:00:00", "id_medicao": 78870, "cod_submercado": null}`

**USI-C01 — Campos de cadastro da usina vazios (nome, município, UF, coordenadas, potência)**  
Tabela: `public.usina` · Afetados: **1** de 10 (10,000%) · Decisão: **SINALIZAR**  
Justificativa: Campo vazio no cadastro não pode ser preenchido sem fonte. O único caso é o cadastro duplicado (USI-U01), que é descartado; os demais seriam apenas sinalizados.
Exemplos: `{"id_fonte": 4, "id_usina": 10, "cod_usina": "CRE-EOL-07", "cod_submercado": "NE"}`

### Consistência


**MED-K01 — Geração solar entre 19h e 5h (sem sol)**  
Tabela: `public.medicao_geracao` · Afetados: **4** de 78.798 (0,005%) · Decisão: **CORRIGIR**  
Justificativa: Física: usina fotovoltaica não gera à noite. O valor é zerado e marcado como CORRIGIDO.
Exemplos: `{"id_usina": 6, "cod_usina": "CRE-UFV-006", "data_hora": "2025-08-12T20:00:00", "id_medicao": 48352, "cod_submercado": "NE"}`; `{"id_usina": 6, "cod_usina": "CRE-UFV-006", "data_hora": "2025-08-12T21:00:00", "id_medicao": 48361, "cod_submercado": "NE"}`; `{"id_usina": 6, "cod_usina": "CRE-UFV-006", "data_hora": "2025-08-12T22:00:00", "id_medicao": 48370, "cod_submercado": "NE"}`

**MED-K02 — Geração maior que zero durante parada registrada da usina**  
Tabela: `public.medicao_geracao` · Afetados: **4** de 78.798 (0,005%) · Decisão: **CORRIGIR**  
Justificativa: Cruzamento entre tabelas: a usina estava em parada programada e a própria linha informa disponibilidade 0 MW. A energia é zerada.
Exemplos: `{"id_usina": 9, "cod_usina": "CRE-UTE-009", "data_hora": "2025-06-05T18:00:00", "id_medicao": 33651, "cod_submercado": "N"}`; `{"id_usina": 9, "cod_usina": "CRE-UTE-009", "data_hora": "2025-06-05T19:00:00", "id_medicao": 33660, "cod_submercado": "N"}`; `{"id_usina": 9, "cod_usina": "CRE-UTE-009", "data_hora": "2025-06-05T20:00:00", "id_medicao": 33669, "cod_submercado": "N"}`

**MED-K03 — Energia maior que a disponibilidade informada na mesma hora**  
Tabela: `public.medicao_geracao` · Afetados: **30** de 78.798 (0,038%) · Decisão: **SINALIZAR**  
Justificativa: Indica erro em uma das duas colunas. Os casos são resolvidos pelas regras MED-A01, MED-A02 e MED-K02; esta regra mede o tamanho do problema.
Exemplos: `{"id_usina": 1, "cod_usina": "CRE-UHE-001", "data_hora": "2025-04-22T14:00:00", "id_medicao": 24104, "cod_submercado": "S"}`; `{"id_usina": 5, "cod_usina": "CRE-BIO-005", "data_hora": "2025-05-10T00:00:00", "id_medicao": 27872, "cod_submercado": "SE"}`; `{"id_usina": 5, "cod_usina": "CRE-BIO-005", "data_hora": "2025-05-10T01:00:00", "id_medicao": 27881, "cod_submercado": "SE"}`

**USI-K01 — Coordenadas fora dos limites da UF declarada**  
Tabela: `public.usina` · Afetados: **2** de 10 (20,000%) · Decisão: **CORRIGIR**  
Justificativa: Quando a latitude com o sinal invertido cai dentro da UF e do município do cadastro, o erro é de sinal (digitação). Corrige-se o sinal; sem isso o clima seria buscado no hemisfério norte.
Exemplos: `{"id_fonte": 3, "id_usina": 4, "cod_usina": "CRE-UFV-004", "cod_submercado": "SE"}`; `{"id_fonte": 5, "id_usina": 5, "cod_usina": "CRE-BIO-005", "cod_submercado": "SE"}`

**USI-K02 — UF incompatível com o município (referência IBGE) ou com o submercado da usina**  
Tabela: `public.usina` · Afetados: **1** de 10 (10,000%) · Decisão: **CORRIGIR**  
Justificativa: O município e as coordenadas apontam para outra UF, que também é a coerente com o submercado. Corrige-se a UF pela tabela de referência de municípios.
Exemplos: `{"id_fonte": 5, "id_usina": 5, "cod_usina": "CRE-BIO-005", "cod_submercado": "SE"}`

### Integridade referencial


**MED-I01 — Medição sem usina ou com usina inexistente no cadastro**  
Tabela: `public.medicao_geracao` · Afetados: **25** de 78.798 (0,032%) · Decisão: **SINALIZAR**  
Justificativa: Não se sabe a qual usina a energia pertence. A linha vai para o DW ligada ao membro 'Desconhecido' (chave -1): o volume fica visível, mas não entra na receita porque não há submercado para buscar o PLD.
Exemplos: `{"id_usina": null, "cod_usina": null, "data_hora": "2025-10-20T14:00:00", "id_medicao": 78870, "cod_submercado": null}`; `{"id_usina": 99, "cod_usina": null, "data_hora": "2025-10-15T00:00:00", "id_medicao": 78871, "cod_submercado": null}`; `{"id_usina": 99, "cod_usina": null, "data_hora": "2025-10-15T01:00:00", "id_medicao": 78872, "cod_submercado": null}`

### Unicidade


**MED-U01 — Mesma usina e hora repetidas com a mesma origem (reprocessamento da integração)**  
Tabela: `public.medicao_geracao` · Afetados: **24** de 78.798 (0,030%) · Decisão: **DESCARTAR**  
Justificativa: As cópias têm a mesma energia e chegaram um dia depois. Mantém-se a primeira leitura recebida; as cópias inflariam a geração e a receita.
Exemplos: `{"id_usina": 4, "cod_usina": "CRE-UFV-004", "data_hora": "2025-01-20T00:00:00", "id_medicao": 78841, "cod_submercado": "SE"}`; `{"id_usina": 4, "cod_usina": "CRE-UFV-004", "data_hora": "2025-01-20T01:00:00", "id_medicao": 78842, "cod_submercado": "SE"}`; `{"id_usina": 4, "cod_usina": "CRE-UFV-004", "data_hora": "2025-01-20T02:00:00", "id_medicao": 78843, "cod_submercado": "SE"}`

**MED-U02 — Lançamento MANUAL por cima de uma leitura SCADA da mesma usina e hora**  
Tabela: `public.medicao_geracao` · Afetados: **4** de 78.798 (0,005%) · Decisão: **QUARENTENA**  
Justificativa: A leitura automática (SCADA) é a medição oficial. O valor manual é 10% maior e não tem justificativa registrada, então vai para quarentena para auditoria em vez de substituir a leitura do medidor.
Exemplos: `{"id_usina": 2, "cod_usina": "CRE-PCH-002", "data_hora": "2025-06-01T08:00:00", "id_medicao": 78865, "cod_submercado": "S"}`; `{"id_usina": 2, "cod_usina": "CRE-PCH-002", "data_hora": "2025-06-01T09:00:00", "id_medicao": 78866, "cod_submercado": "S"}`; `{"id_usina": 2, "cod_usina": "CRE-PCH-002", "data_hora": "2025-06-01T10:00:00", "id_medicao": 78867, "cod_submercado": "S"}`

**USI-U01 — Mesma usina cadastrada mais de uma vez (nome normalizado, fonte, coordenadas e potência iguais)**  
Tabela: `public.usina` · Afetados: **2** de 10 (20,000%) · Decisão: **DESCARTAR**  
Justificativa: A segunda linha é uma cópia feita às pressas (código fora do padrão, nome com espaço extra, município vazio). Mantém-se o cadastro original e o id duplicado é mapeado para ele em tratado.mapa_usina, para nenhuma medição se perder.
Exemplos: `{"id_fonte": 4, "id_usina": 7, "cod_usina": "CRE-EOL-007", "cod_submercado": "NE"}`; `{"id_fonte": 4, "id_usina": 10, "cod_usina": "CRE-EOL-07", "cod_submercado": "NE"}`

### Validade


**MED-V01 — Energia gerada negativa**  
Tabela: `public.medicao_geracao` · Afetados: **4** de 78.798 (0,005%) · Decisão: **CORRIGIR**  
Justificativa: Valor negativo é consumo dos serviços auxiliares, não geração. Para o indicador de geração e receita ele vira 0; o valor original fica guardado em energia_original_mwh.
Exemplos: `{"id_usina": 7, "cod_usina": "CRE-EOL-007", "data_hora": "2025-02-03T01:00:00", "id_medicao": 7143, "cod_submercado": "NE"}`; `{"id_usina": 7, "cod_usina": "CRE-EOL-007", "data_hora": "2025-02-03T02:00:00", "id_medicao": 7152, "cod_submercado": "NE"}`; `{"id_usina": 7, "cod_usina": "CRE-EOL-007", "data_hora": "2025-02-03T03:00:00", "id_medicao": 7161, "cod_submercado": "NE"}`

**MED-V02 — Data da medição fora do período de 2025**  
Tabela: `public.medicao_geracao` · Afetados: **1** de 78.798 (0,001%) · Decisão: **QUARENTENA**  
Justificativa: Ano 2052 é erro de digitação. A hora provável (mesmo dia e hora em 2025) já tem leitura SCADA, então corrigir o ano criaria uma duplicata; o registro vai para quarentena.
Exemplos: `{"id_usina": 6, "cod_usina": "CRE-UFV-006", "data_hora": "2052-05-14T10:00:00", "id_medicao": 78869, "cod_submercado": "NE"}`

**MED-V03 — Dado recebido antes da hora medida (recebido_em < data_hora)**  
Tabela: `public.medicao_geracao` · Afetados: **25** de 78.798 (0,032%) · Decisão: **SINALIZAR**  
Justificativa: Impossível no mundo real: o erro está no relógio do servidor de integração, não na energia. A medição é mantida e sinalizada.
Exemplos: `{"id_usina": 2, "cod_usina": "CRE-PCH-002", "data_hora": "2025-08-05T00:00:00", "id_medicao": 46659, "cod_submercado": "S"}`; `{"id_usina": 2, "cod_usina": "CRE-PCH-002", "data_hora": "2025-08-05T01:00:00", "id_medicao": 46668, "cod_submercado": "S"}`; `{"id_usina": 2, "cod_usina": "CRE-PCH-002", "data_hora": "2025-08-05T02:00:00", "id_medicao": 46677, "cod_submercado": "S"}`

**PAR-V01 — Parada com fim anterior ao início**  
Tabela: `public.parada_usina` · Afetados: **1** de 11 (9,091%) · Decisão: **QUARENTENA**  
Justificativa: Lançamento manual inconsistente. Inverter as datas seria um palpite, e as medições do período mostram a usina gerando normalmente, então a parada não é usada no cálculo de perdas e fica guardada para conferência com a operação.
Exemplos: `{"id_usina": 4, "id_parada": 11}`

**USI-V01 — Código da usina fora do padrão CRE-XXX-999**  
Tabela: `public.usina` · Afetados: **1** de 10 (10,000%) · Decisão: **DESCARTAR**  
Justificativa: O código é a chave de negócio usada no DW; um código fora do padrão indica cadastro irregular (é a mesma linha duplicada de USI-U01).
Exemplos: `{"id_fonte": 4, "id_usina": 10, "cod_usina": "CRE-EOL-07", "cod_submercado": "NE"}`

**USI-V02 — Data de início de operação no futuro ou posterior à primeira medição**  
Tabela: `public.usina` · Afetados: **1** de 10 (10,000%) · Decisão: **CORRIGIR**  
Justificativa: Uma usina não gera antes de começar a operar. A data verdadeira não está disponível, então ela é anulada (vira 'desconhecida' no DW) em vez de inventada. As medições são mantidas.
Exemplos: `{"id_fonte": 3, "id_usina": 6, "cod_usina": "CRE-UFV-006", "cod_submercado": "NE"}`

## 4. Regras executadas sem ocorrência

Estas regras rodam em toda carga e protegem contra problemas que não apareceram nesta execução.

| Regra | Dimensão | Tabela | Descrição |
|---|---|---|---|
| CLI-A01 | Acurácia | tratado.clima_horario | Vento idêntico por 24 horas ou mais (série congelada) |
| PLD-A01 | Acurácia | tratado.pld_horario | PLD muito distante do padrão do mês no submercado (z robusto > 6) |
| CLI-T01 | Atualidade | tratado.clima_horario | Usina cujo clima termina antes do fim do período configurado |
| CLI-C01 | Completude | tratado.clima_horario | Horas sem clima por usina no período baixado |
| CLI-C02 | Completude | tratado.clima_horario | Variáveis de clima nulas |
| FER-C01 | Completude | public.feriado_nacional | Anos cobertos pelos fatos (geração e PLD) sem feriados cadastrados |
| PLD-C01 | Completude | tratado.pld_horario | Horas sem PLD por submercado nos meses publicados |
| SUB-C01 | Completude | public.submercado | Submercados do SIN ausentes no cadastro (esperados SE, S, NE, N) |
| CLI-K01 | Consistência | tratado.clima_horario | Radiação solar acima de 50 W/m² entre 0h e 4h (fuso horário trocado) |
| MED-K04 | Consistência | public.medicao_geracao | Medição sem PLD publicado para o submercado e a hora |
| PAR-K01 | Consistência | public.parada_usina | Paradas sobrepostas para a mesma usina |
| PLD-K01 | Consistência | raw.ccee_pld_horario | MES_REFERENCIA ou PERIODO_COMERCIALIZACAO incoerentes com DIA e HORA |
| CLI-I01 | Integridade referencial | tratado.clima_horario | Ponto de clima sem usina correspondente no cadastro tratado |
| PAR-I01 | Integridade referencial | public.parada_usina | Parada de usina inexistente no cadastro |
| CLI-U01 | Unicidade | tratado.clima_horario | Mesma usina e hora repetidas no clima |
| PLD-U01 | Unicidade | raw.ccee_pld_horario | Mesmo submercado e hora repetidos no raw da API |
| CLI-V01 | Validade | tratado.clima_horario | Clima fora da faixa física (radiação 0 a 1.400 W/m², vento 0 a 60 m/s, temperatura -10 a 50 °C) |
| FER-V01 | Validade | public.feriado_nacional | Tipo de feriado fora do domínio ('Feriado' ou 'Ponto facultativo') |
| FON-V01 | Validade | public.fonte_energia | Fonte com classificação inválida (intermitente não renovável ou código fora do domínio) |
| PLD-V01 | Validade | tratado.pld_horario | PLD fora dos limites regulatórios do ano (piso e teto horário da ANEEL) |
| PLD-V02 | Validade | raw.ccee_pld_horario | Registro do raw com submercado, data, hora ou valor que não pode ser convertido |
| USI-V03 | Validade | public.usina | Potência instalada nula, zero ou negativa |

## 5. Quarentena

| Tabela | Regra | Registros | Motivo |
|---|---|---|---|
| medicao_geracao | MED-U02 | 4 | lancamento manual sobre leitura SCADA |
| medicao_geracao | MED-V02 | 1 | data fora do periodo de 2025 |
| parada_usina | PAR-V01 | 1 | fim anterior ao inicio |

## 6. Impacto da limpeza nos indicadores de negócio (antes × depois)

**Antes** = soma ingênua da tabela de origem (como um analista faria sem tratar nada). **Depois** = dado tratado que alimenta o DW (sem medições de usina desconhecida).

| Indicador | Recorte | Antes | Depois | Diferença | Variação (%) |
|---|---|---|---|---|---|
| Geração (MWh) | Fonte BIO | 927.792,19 | 185.989,74 | -741.802,45 | -79,95 |
| Geração (MWh) | Fonte EOL | 629.673,66 | 629.202,32 | -471,33 | -0,07 |
| Geração (MWh) | Fonte PCH | 130.846,39 | 130.789,90 | -56,48 | -0,04 |
| Geração (MWh) | Fonte UFV | 281.523,13 | 281.055,97 | -467,16 | -0,17 |
| Geração (MWh) | Fonte UHE | 1.514.383,16 | 1.513.786,10 | -597,07 | -0,04 |
| Geração (MWh) | Fonte UTE | 381.407,90 | 380.879,90 | -528,00 | -0,14 |
| Geração (MWh) | TOTAL | 3.867.483,09 | 3.121.703,93 | -745.779,16 | -19,28 |
| Geração sem usina identificada (MWh) | TOTAL | 1.856,66 | 1.856,66 | 0,00 | 0,00 |
| Linhas de medição | TOTAL | 78.798,00 | 78.744,00 | -54,00 | -0,07 |
| Preço capturado (R$/MWh) | Fonte BIO | 183,98 | 220,76 | 36,78 | 19,99 |
| Preço capturado (R$/MWh) | Fonte EOL | 211,45 | 211,42 | -0,02 | -0,01 |
| Preço capturado (R$/MWh) | Fonte PCH | 187,48 | 187,49 | 0,01 | 0,01 |
| Preço capturado (R$/MWh) | Fonte UFV | 151,67 | 151,69 | 0,02 | 0,02 |
| Preço capturado (R$/MWh) | Fonte UHE | 185,30 | 185,31 | 0,01 | 0,00 |
| Preço capturado (R$/MWh) | Fonte UTE | 240,69 | 240,64 | -0,06 | -0,02 |
| Preço capturado (R$/MWh) | TOTAL | 192,33 | 196,50 | 4,17 | 2,17 |
| Receita valorada ao PLD (R$) | Fonte BIO | 170.693.739,16 | 41.059.493,96 | -129.634.245,20 | -75,95 |
| Receita valorada ao PLD (R$) | Fonte EOL | 133.143.397,32 | 133.028.897,37 | -114.499,95 | -0,09 |
| Receita valorada ao PLD (R$) | Fonte PCH | 24.530.600,77 | 24.521.739,43 | -8.861,34 | -0,04 |
| Receita valorada ao PLD (R$) | Fonte UFV | 42.689.017,48 | 42.633.338,28 | -55.679,20 | -0,13 |
| Receita valorada ao PLD (R$) | Fonte UHE | 280.615.292,45 | 280.515.740,17 | -99.552,28 | -0,04 |
| Receita valorada ao PLD (R$) | Fonte UTE | 91.802.595,84 | 91.653.779,05 | -148.816,80 | -0,16 |
| Receita valorada ao PLD (R$) | TOTAL | 743.474.643,02 | 613.412.988,25 | -130.061.654,78 | -17,49 |

## 7. Situação das medições após a limpeza

| Status | Linhas |
|---|---|
| OK | 78316 |
| SINALIZADO | 384 |
| CORRIGIDO | 37 |
| DESCONHECIDA | 25 |
| ESTIMADO | 7 |

## 8. Profiling da tabela de medição (origem)

O profiling completo de todas as tabelas está em `qualidade.profiling`.

| coluna | tipo | total | nulos | distintos | minimo | maximo | media | mediana |
|---|---|---|---|---|---|---|---|---|
| data_hora | datetime64[us] | 78798 | 0 | 8761 | 2025-01-01 00:00:00 | 2052-05-14 10:00:00 |  |  |
| disponibilidade_mw | float64 | 78798 | 1 | 10 | 0.0 | 180.0 | 89.8 | 90.0 |
| energia_mwh | float64 | 78798 | 6 | 44288 | -0.85 | 33963.0 | 49.085 | 27.831 |
| id_medicao | int64 | 78798 | 0 | 78798 | 1 | 78894 | 39403.191 | 39399.5 |
| id_usina | float64 | 78798 | 1 | 10 | 1.0 | 99.0 | 5.03 | 5.0 |
| origem | str | 78798 | 0 | 2 | MANUAL | SCADA |  |  |
| recebido_em | datetime64[us] | 78798 | 0 | 71144 | 2025-01-01 01:07:00 | 2026-02-10 09:23:00 |  |  |

## 9. Últimas execuções do pipeline (controle.log_execucao)

| processo | fonte | status | linhas_lidas | linhas_gravadas | inicio | mensagem |
|---|---|---|---|---|---|---|
| carga_dw | tratado -> dw_campo_real | SUCESSO | 113809 | 203319 | 12/11/2026 22:15 |  |
| extracao_clima | Open-Meteo | SUCESSO | 8760 | 8760 | 12/11/2026 21:54 |  |
| extracao_pld | CCEE | SEM_DADOS | 0 | 0 | 12/11/2026 22:07 | Nenhum recurso do PLD horario encontrado para 2026 |
| pld_simulado | Plano B do script da professora (passo 4.9) | SUCESSO | 35040 | 35040 | 12/11/2026 22:15 | PLD SIMULADO gravado em 35040 horas; 0 horas ja tinham PLD real da CCEE e foram mantidas. Ao rodar a etapa 'pld' com a API disponivel, o dado real substitui o s |
| qualidade_clima | tratado.clima_horario | SUCESSO | 78840 | 78840 | 12/11/2026 21:54 |  |
| qualidade_origem | public + tratado.pld_horario | SUCESSO | 113882 | 78801 | 12/11/2026 22:15 | 6 registros em quarentena; 1 usina(s) duplicada(s) mapeada(s) |
| transformacao_clima | raw.openmeteo_clima | SUCESSO | 78840 | 78840 | 12/11/2026 21:54 |  |
| transformacao_pld | raw.ccee_pld_horario | SEM_DADOS | 0 | 0 | 12/11/2026 22:07 |  |
