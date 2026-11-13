# Guia do Painel Power BI — Campo Real Energia

O painel lê **somente** o schema `dw_campo_real`. Nenhuma tabela de `public`, `raw`, `tratado` ou `qualidade` entra no modelo.

Arquivo final: `powerbi/painel_campo_real.pbix`

---

## 1. Conectar no banco

1. **Página Inicial → Obter dados → Mais… → Banco de dados PostgreSQL**.
2. **Servidor**: o host do banco.
   - Neon: o host da string de conexão, ex.: `ep-xxxx-123456.sa-east-1.aws.neon.tech` (sem `postgresql://`, sem usuário e sem `/neondb`).
   - Local: `localhost:5432`.
3. **Banco de dados**: `neondb` no Neon, ou `campo_real_energia` no local.
4. **Modo de conectividade**: **Importar**.
5. Credenciais: aba **Banco de dados**, com usuário e senha. Se perguntar sobre criptografia, mantenha a conexão criptografada (o Neon exige SSL).
6. No Navegador, marque só as tabelas que começam com `dw_campo_real.`:
   - `dim_tempo`, `dim_usina`, `dim_submercado`, `dim_regra_qualidade`
   - `fato_geracao_horaria`, `fato_pld_horario`, `fato_clima_horario`, `fato_parada_horaria`, `fato_qualidade_regra`
   - `agg_impacto_limpeza`, `vw_geracao_clima`
7. Clique em **Carregar**.

> Se der erro de certificado ou SSL, atualize o Power BI Desktop: as versões recentes já trazem o driver do PostgreSQL.

---

## 2. Relacionamentos (Exibição de modelo)

O Power BI costuma detectar os relacionamentos sozinho, porque as chaves têm o mesmo nome. Confira se ficaram exatamente assim, todos **1 : N** e com **filtro em direção única** (da dimensão para o fato):

| Dimensão (1) | Fato (N) | Coluna |
|---|---|---|
| dim_tempo | fato_geracao_horaria | sk_tempo |
| dim_tempo | fato_pld_horario | sk_tempo |
| dim_tempo | fato_clima_horario | sk_tempo |
| dim_tempo | fato_parada_horaria | sk_tempo |
| dim_tempo | vw_geracao_clima | sk_tempo |
| dim_usina | fato_geracao_horaria | sk_usina |
| dim_usina | fato_clima_horario | sk_usina |
| dim_usina | fato_parada_horaria | sk_usina |
| dim_usina | vw_geracao_clima | sk_usina |
| dim_submercado | fato_geracao_horaria | sk_submercado |
| dim_submercado | fato_pld_horario | sk_submercado |
| dim_submercado | fato_clima_horario | sk_submercado |
| dim_submercado | fato_parada_horaria | sk_submercado |
| dim_regra_qualidade | fato_qualidade_regra | sk_regra |

Apague qualquer relacionamento que o Power BI tenha criado entre dois fatos.

Ajustes rápidos:
- `dim_tempo[nome_mes]` → **Classificar por coluna** → `mes`.
- `dim_tempo[nome_dia_semana]` → **Classificar por coluna** → `dia_semana`.
- `dim_tempo[mes_abrev]` → **Classificar por coluna** → `mes`.
- Oculte as colunas `sk_*` dos fatos (botão direito → Ocultar na exibição de relatório).

---

## 3. Medidas DAX

Crie uma tabela vazia para guardar as medidas: **Página Inicial → Inserir dados**, nome `_Medidas`, OK. Depois, em cada medida: **Ferramentas de tabela → Nova medida** e cole o código.

### Geração (P1)

```DAX
Geração (MWh) = SUM ( fato_geracao_horaria[energia_mwh] )
```
```DAX
Geração (GWh) = DIVIDE ( [Geração (MWh)], 1000 )
```
```DAX
Capacidade (MWh) = SUM ( fato_geracao_horaria[capacidade_mwh] )
```
```DAX
Fator de Capacidade = DIVIDE ( [Geração (MWh)], [Capacidade (MWh)] )
```
Formato: Porcentagem.

### Valor da geração (P2 e P3)

```DAX
Receita Valorada (R$) = SUM ( fato_geracao_horaria[receita_rs] )
```
```DAX
Receita Valorada (R$ mi) = DIVIDE ( [Receita Valorada (R$)], 1000000 )
```
```DAX
Geração Valorada (MWh) =
CALCULATE (
    [Geração (MWh)],
    NOT ISBLANK ( fato_geracao_horaria[receita_rs] )
)
```
```DAX
Preço Capturado (R$/MWh) = DIVIDE ( [Receita Valorada (R$)], [Geração Valorada (MWh)] )
```
```DAX
Receita Perfil Plano (R$) = SUM ( fato_geracao_horaria[receita_perfil_plano_rs] )
```
```DAX
Razão de Captura = DIVIDE ( [Receita Valorada (R$)], [Receita Perfil Plano (R$)] )
```
Formato: Decimal com 2 casas. Acima de 1 significa que a fonte gera nas horas caras; abaixo de 1, nas horas baratas.

### Preço (P4)

```DAX
PLD Médio (R$/MWh) = AVERAGE ( fato_pld_horario[pld_rs_mwh] )
```
```DAX
% Horas no Piso =
DIVIDE (
    COUNTROWS ( FILTER ( fato_pld_horario, fato_pld_horario[flag_piso] ) ),
    COUNTROWS ( fato_pld_horario )
)
```
```DAX
Fator de Capacidade Médio Horário =
AVERAGEX (
    fato_geracao_horaria,
    DIVIDE ( fato_geracao_horaria[energia_mwh], fato_geracao_horaria[capacidade_mwh] )
)
```

### Paradas (P5)

```DAX
Horas Indisponíveis = SUM ( fato_parada_horaria[horas_indisponiveis] )
```
```DAX
Energia Não Gerada (MWh) = SUM ( fato_parada_horaria[energia_esperada_mwh] )
```
```DAX
Receita Perdida (R$) = SUM ( fato_parada_horaria[receita_perdida_rs] )
```
```DAX
Receita Perdida (R$ mil) = DIVIDE ( [Receita Perdida (R$)], 1000 )
```

### Clima (P6)

```DAX
Radiação Média (W/m²) = AVERAGE ( vw_geracao_clima[radiacao_w_m2] )
```
```DAX
Vento Médio (m/s) = AVERAGE ( vw_geracao_clima[vento_100m_ms] )
```
```DAX
Geração com Clima (MWh) = SUM ( vw_geracao_clima[energia_mwh] )
```
```DAX
Correlação Radiação x Geração =
VAR t = FILTER ( vw_geracao_clima, NOT ISBLANK ( vw_geracao_clima[radiacao_w_m2] ) && NOT ISBLANK ( vw_geracao_clima[energia_mwh] ) )
VAR mx = AVERAGEX ( t, vw_geracao_clima[radiacao_w_m2] )
VAR my = AVERAGEX ( t, vw_geracao_clima[energia_mwh] )
VAR cov = SUMX ( t, ( vw_geracao_clima[radiacao_w_m2] - mx ) * ( vw_geracao_clima[energia_mwh] - my ) )
VAR sx = SQRT ( SUMX ( t, ( vw_geracao_clima[radiacao_w_m2] - mx ) ^ 2 ) )
VAR sy = SQRT ( SUMX ( t, ( vw_geracao_clima[energia_mwh] - my ) ^ 2 ) )
RETURN DIVIDE ( cov, sx * sy )
```
```DAX
Correlação Vento x Geração =
VAR t = FILTER ( vw_geracao_clima, NOT ISBLANK ( vw_geracao_clima[vento_100m_ms] ) && NOT ISBLANK ( vw_geracao_clima[energia_mwh] ) )
VAR mx = AVERAGEX ( t, vw_geracao_clima[vento_100m_ms] )
VAR my = AVERAGEX ( t, vw_geracao_clima[energia_mwh] )
VAR cov = SUMX ( t, ( vw_geracao_clima[vento_100m_ms] - mx ) * ( vw_geracao_clima[energia_mwh] - my ) )
VAR sx = SQRT ( SUMX ( t, ( vw_geracao_clima[vento_100m_ms] - mx ) ^ 2 ) )
VAR sy = SQRT ( SUMX ( t, ( vw_geracao_clima[energia_mwh] - my ) ^ 2 ) )
RETURN DIVIDE ( cov, sx * sy )
```

### Confiança nos números (P7)

```DAX
Registros Avaliados =
CALCULATE ( SUM ( fato_qualidade_regra[registros_avaliados] ), fato_qualidade_regra[flag_ultima_execucao] = TRUE () )
```
```DAX
Registros com Falha =
CALCULATE ( SUM ( fato_qualidade_regra[registros_falha] ), fato_qualidade_regra[flag_ultima_execucao] = TRUE () )
```
```DAX
Índice de Qualidade = 1 - DIVIDE ( [Registros com Falha], [Registros Avaliados] )
```
Formato: Porcentagem com 2 casas.
```DAX
Receita Antes da Limpeza (R$ mi) =
DIVIDE (
    CALCULATE ( SUM ( agg_impacto_limpeza[antes] ), agg_impacto_limpeza[indicador] = "receita_valorada_rs", agg_impacto_limpeza[recorte_tipo] = "TOTAL" ),
    1000000
)
```
```DAX
Receita Depois da Limpeza (R$ mi) =
DIVIDE (
    CALCULATE ( SUM ( agg_impacto_limpeza[depois] ), agg_impacto_limpeza[indicador] = "receita_valorada_rs", agg_impacto_limpeza[recorte_tipo] = "TOTAL" ),
    1000000
)
```
```DAX
Receita Inflada pelos Erros (R$ mi) = [Receita Antes da Limpeza (R$ mi)] - [Receita Depois da Limpeza (R$ mi)]
```

---

## 4. Páginas do relatório (história para a diretoria)

Em **todas as páginas**, coloque no painel de filtros (**Filtros nesta página**):
- `dim_tempo[ano]` = 2025 nas páginas de geração (o PLD vai até 2026, mas a geração é só de 2025).
- `dim_usina[cod_usina]` diferente de `DESCONHECIDA` (exceto na página 7).

E em todas as páginas, uma **caixa de texto no rodapé**:
> Fontes: CCEE – PLD horário (dadosabertos.ccee.org.br, licença CC-BY 4.0) · Open-Meteo.com – Historical Weather API (CC-BY 4.0) · Dados operacionais: Campo Real Energia (fictícios).

**Origem do PLD:** enquanto a CCEE estiver bloqueando a extração, o PLD de 2025 é o simulado do plano B. Em todas as páginas com receita ou preço, adicione um **Cartão** com a medida abaixo, para a diretoria saber de onde vem o preço:
```DAX
Origem do PLD =
IF (
    CALCULATE ( COUNTROWS ( fato_pld_horario ), fato_pld_horario[origem_pld] = "SIMULADO" ) > 0,
    "PLD SIMULADO (plano B) — CCEE bloqueou a API",
    "PLD real da CCEE"
)
```

Cores fixas por fonte (Formatar → Cores dos dados), para o mesmo padrão em todo o painel:
Hidrelétrica `#1f6fb2` · PCH `#5aa0d8` · Eólica `#2e9e6a` · Solar `#f2a900` · Biomassa `#8a6d3b` · Térmica `#c0392b`.

### Página 1 — "Quanto a nossa geração vale?" (abertura)
- 4 **Cartões**: `Geração (GWh)`, `Receita Valorada (R$ mi)`, `Preço Capturado (R$/MWh)`, `Índice de Qualidade`.
- **Gráfico de colunas empilhadas**: eixo `dim_tempo[mes_abrev]`, valores `Receita Valorada (R$ mi)`, legenda `dim_usina[fonte]`.
- Título da página como pergunta: *"Quanto a nossa geração vale a preço de mercado?"*

### Página 2 — P1: Quanto geramos?
- **Gráfico de barras**: eixo `dim_usina[nome]`, valor `Geração (GWh)`, ordenado do maior para o menor.
- **Gráfico de linhas**: eixo `dim_tempo[mes_abrev]`, valor `Geração (GWh)`, legenda `dim_usina[fonte]`.
- **Matriz**: linhas `dim_usina[fonte]` › `dim_usina[nome]`, colunas `dim_submercado[nome]`, valores `Geração (GWh)` e `Fator de Capacidade`.
- **Segmentação**: `dim_submercado[nome]`.

### Página 3 — P2 e P3: Quanto vale e qual fonte captura o melhor preço?
- **Gráfico de barras**: eixo `dim_usina[fonte]`, valor `Razão de Captura`. Em **Análise → Linha constante = 1** (rótulo "preço médio").
- **Gráfico de barras**: eixo `dim_usina[fonte]`, valor `Preço Capturado (R$/MWh)`.
- **Tabela**: `dim_usina[fonte]`, `Geração (GWh)`, `Receita Valorada (R$ mi)`, `Preço Capturado (R$/MWh)`, `Razão de Captura`.
- **Caixa de texto** explicando: razão de captura = receita real ÷ receita se o preço fosse a média do mês.

### Página 4 — P4: Quando o PLD é alto, e nós geramos nesses momentos?
- **Matriz (mapa de calor)**: linhas `dim_tempo[hora]`, colunas `dim_tempo[mes_abrev]`, valor `PLD Médio (R$/MWh)`. Em **Formatar → Elementos de célula → Cor da tela de fundo → ativar** (escala do branco ao vermelho).
- **Gráfico de linhas e colunas**: eixo `dim_tempo[hora]`, colunas `Fator de Capacidade Médio Horário` com legenda `dim_usina[fonte]` (ou linhas), linha `PLD Médio (R$/MWh)` no eixo secundário. Deixe só Solar, Eólica e Térmica no filtro do visual para ficar legível.
- **Cartão**: `% Horas no Piso`.
- **Segmentação**: `dim_submercado[nome]`, `dim_tempo[ano]` (nesta página pode deixar 2025 e 2026).

### Página 5 — P5: Quanto perdemos com paradas?
- 3 **Cartões**: `Horas Indisponíveis`, `Energia Não Gerada (MWh)`, `Receita Perdida (R$ mil)`.
- **Gráfico de barras empilhadas**: eixo `dim_usina[nome]`, valor `Receita Perdida (R$ mil)`, legenda `fato_parada_horaria[tipo_parada]`.
- **Tabela**: `dim_usina[nome]`, `fato_parada_horaria[motivo]`, `fato_parada_horaria[tipo_parada]`, `Horas Indisponíveis`, `Energia Não Gerada (MWh)`, `Receita Perdida (R$ mil)`.

### Página 6 — P6: O clima explica a nossa geração?
- **Gráfico de dispersão**: eixo X `Radiação Média (W/m²)`, eixo Y `Geração com Clima (MWh)`, **Valores** `dim_tempo[data]` (um ponto por dia), filtro do visual `dim_usina[cod_fonte]` = UFV.
- **Gráfico de dispersão**: eixo X `Vento Médio (m/s)`, eixo Y `Geração com Clima (MWh)`, **Valores** `dim_tempo[data]`, filtro `dim_usina[cod_fonte]` = EOL.
- 2 **Cartões**: `Correlação Radiação x Geração` (filtro UFV) e `Correlação Vento x Geração` (filtro EOL).

### Página 7 — P7: Podemos confiar nesses números?
- **Gráfico de barras**: eixo `dim_regra_qualidade[dimensao]`, valor `Índice de Qualidade`. Eixo X de 99% a 100%, para a diferença aparecer.
- **Tabela**: `dim_regra_qualidade[cod_regra]`, `[descricao]`, `[acao]`, `Registros com Falha`, com filtro `Registros com Falha > 0`.
- 3 **Cartões**: `Receita Antes da Limpeza (R$ mi)`, `Receita Depois da Limpeza (R$ mi)`, `Receita Inflada pelos Erros (R$ mi)`.
- **Gráfico de barras agrupadas**: `agg_impacto_limpeza`, com filtro `indicador = geracao_mwh` e `recorte_tipo = FONTE`, eixo `recorte`, valores `antes` e `depois`.

### Página 8 — Recomendação
Só caixas de texto, com 3 ou 4 recomendações curtas (ver o roteiro da apresentação).

---

## 5. Salvar e entregar
- **Arquivo → Salvar como** → `powerbi/painel_campo_real.pbix`.
- Antes de salvar, **Página Inicial → Atualizar** para garantir que os números são os da última carga.
