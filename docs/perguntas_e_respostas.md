# Perguntas prováveis na apresentação (e como responder)

## Modelagem

**Qual é o grão da fato de geração?**
Uma usina em uma hora. Cada linha é quanto aquela usina gerou naquela hora.

**E da fato de preço?**
Um submercado em uma hora. O PLD não tem usina, ele vale para o submercado inteiro.

**Por que o submercado é uma dimensão separada e não só um campo da usina?**
Porque o PLD é por submercado. Para cruzar geração com preço, os dois fatos precisam da mesma dimensão (dimensão conformada). Se o submercado estivesse só dentro da usina, a fato de preço não teria como se ligar.

**Por que a fonte de energia está dentro da dim_usina?**
São só 6 fontes e toda fonte é acessada pela usina. Separar viraria snowflake sem ganho nenhum.

**Por que a receita já vem calculada no fato e não no Power BI?**
A receita é a soma de geração × PLD **hora a hora**. Se eu somar a geração do mês e multiplicar pelo PLD médio, o número sai errado, porque a usina não gera igual em todas as horas. Então eu faço o produto na carga, no grão horário, e a receita fica uma medida que dá para somar.

**Qual SCD vocês usaram?**
Os dois, dependendo do atributo. Potência, nome, situação, fonte e submercado são tipo 2 (cria versão nova), porque mudam a análise do passado: o fator de capacidade de 2025 tem que usar a potência de 2025. Já UF, município e coordenadas são tipo 1 (sobrescreve), porque são correções de erro, a usina não mudou de lugar. *(Dá para mostrar o `sql/90_demo_scd2.sql`.)*

**O que é o membro desconhecido? Teve algum caso?**
É a linha com chave −1 em cada dimensão. Teve sim: 25 medições sem usina válida (id 99, que não existe, e uma com id nulo). Elas entram no DW apontando para "Usina desconhecida", o volume aparece no painel, mas não entra na receita, porque sem submercado não tem PLD.

**Como vocês ligaram o clima à usina?**
Eu busquei o clima no Open-Meteo nas coordenadas exatas de cada usina, então cada ponto de clima é uma usina. Por isso a fato de clima tem o mesmo grão da geração (usina × hora). E usei as coordenadas **depois** da limpeza: uma usina estava com a latitude sem o sinal de menos, e sem a correção o clima viria do hemisfério norte.

**Como trataram as paradas, que têm início e fim?**
Eu "explodi" cada parada em horas. Cada hora parada virou uma linha na fato de paradas, assim ela cruza com o PLD e com o tempo no mesmo grão.

**Como calcularam a energia perdida?**
Média do que a usina gerou no mesmo mês e na mesma hora do dia, fora de parada, vezes o PLD da hora. A biomassa parou dezembro inteiro, então não tem referência e a perda fica zero. Faz sentido, porque é entressafra e ela quase não gera.

**O que tem na dimensão de tempo?**
Hora, dia, mês, dia útil, feriado, estação do ano, período úmido/seco e patamar de carga (leve, médio, pesado), que é uma simplificação do padrão do ONS.

**De onde vieram os feriados de 2026?**
A origem só tinha 2025, mas o PLD vai até 2026. Isso foi uma regra de completude (FER-C01). Eu calculei os feriados nacionais de 2026 pelo calendário oficial (datas fixas e as móveis a partir da Páscoa) e marquei como CALCULADO.

## Extração

**Como funciona a paginação da API da CCEE?**
Primeiro peço com `limit=0` para saber o total. Depois vou pedindo de 5.000 em 5.000, aumentando o `offset`, ordenado por `_id`, até chegar no total. Se vier uma página vazia antes, eu paro e registro aviso.

**Como acharam o resource_id de cada ano?**
O código chama `package_show` do dataset `pld_horario` e procura o ano no nome de cada recurso. Se essa chamada falhar, usa o id que está no `config.ini`.

**E se a API cair?**
Tenta de novo com espera crescente. Se mesmo assim falhar, grava FALHA no log com o erro, e o pipeline continua com o último dado que já estava no raw. Eu testei isso.

**Por que o PLD está simulado?**
A CCEE passou a bloquear a API para requisições feitas por programa (HTTP 403, "acesso bloqueado por políticas de segurança"), tanto do Colab quanto da minha rede de casa. Pelo navegador funciona. O pipeline fez o que tinha que fazer: registrou FALHA no log e não travou. Não tentei burlar o bloqueio, porque é uma política de segurança deles. Abri chamado e usei o plano B que está no próprio script da professora, com o PLD simulado marcado como SIMULADO no banco e no painel. Quando a CCEE liberar, basta rodar a etapa `pld` e o dado real substitui o simulado sozinho.

**E o limite de requisições?**
Tem uma pausa entre as chamadas e, se a API responder 429, eu espero o tempo que ela mandar no `Retry-After`.

**Como vocês evitam baixar tudo de novo?**
Antes de baixar, o código compara o que já tem no raw com o total da API. Se já está completo, nem baixa (status CACHE). Se faltar um pedaço, continua de onde parou.

**Qual a diferença entre raw e tratado?**
O raw é o dado exatamente como chegou da API (o JSON inteiro), com a hora e a URL da extração. O tratado tem os tipos certos, chave primária e o grão definido.

**Onde ficam as senhas?**
No `.env`, que está no `.gitignore`. O código lê dali, nada fica fixo no código.

## Qualidade

**Quantas regras e quais dimensões?**
47 regras, cobrindo as 7 dimensões (completude, unicidade, validade, consistência, acurácia, integridade referencial e atualidade). Elas são funções reutilizáveis em `verificacoes.py`, e cada regra só chama essas funções com parâmetros.

**Qual foi o problema mais grave?**
Um dia de biomassa lançado em kWh em vez de MWh. Esse dia sozinho fazia a geração do ano aparecer 24% maior (3.867 GWh em vez de 3.122) e a receita 21% maior (R$ 743 mi em vez de R$ 613 mi). Sem a limpeza, a diretoria veria R$ 130 milhões que não existem.

**Diferença entre corrigir, descartar, quarentena e sinalizar?**
- **Corrigir**: quando tenho certeza do erro e de como consertar (kWh → MWh, geração negativa → 0, solar de noite → 0). O valor original fica guardado.
- **Descartar**: cópia idêntica (reprocessamento duplicou um dia inteiro).
- **Quarentena**: não sei qual é o certo, então tiro do caminho e guardo (lançamento manual por cima do SCADA, ano 2052, parada com fim antes do início).
- **Sinalizar**: o dado está plausível ou não tenho como substituir, então mantenho e marco (medidor travado, dado que chegou atrasado).

**Por que não corrigiram o ano 2052 para 2025?**
Porque a hora correta (14/05/2025 10h) já tinha leitura do SCADA. Corrigir criaria uma duplicata.

**Por que interpolaram a hidrelétrica e não o dia que faltou da eólica?**
A hidrelétrica tinha 6 horas nulas e gera de forma estável, então interpolar é uma estimativa segura. Um dia inteiro de vento não dá para adivinhar, então só sinalizei.

**Como souberam que era vírgula deslocada e não pico de leitura?**
Dividi por 10 e comparei com as horas vizinhas. Na hidrelétrica bateu, então era vírgula. Na eólica (499 MWh numa usina de 50 MW) não bateu, então era pico, e estimei pela média das vizinhas.

**Como mediram o impacto da limpeza?**
Calculei os indicadores duas vezes: com o dado bruto, somando tudo como um analista faria sem tratar, e com o dado limpo. A diferença está na tabela `qualidade.impacto_limpeza` e no painel.

**Vocês alteraram as tabelas de origem?**
Não. A origem só é lida. Toda a limpeza acontece no schema `tratado`.

**Como é calculado o índice de qualidade?**
100% menos (registros com falha ÷ registros avaliados), por dimensão e por tabela.

## Negócio

**O que é razão de captura?**
É quanto a fonte recebeu ÷ quanto receberia se o preço fosse sempre a média do mês. Acima de 1, ela gera nas horas caras. Abaixo de 1, nas horas baratas.

**Por que a solar captura pior?**
Porque ela gera no meio do dia, justamente quando o PLD cai (tem muita solar no sistema). A térmica faz o contrário: gera no horário de ponta, quando o preço sobe.

**Como garantem que o painel lê só do DW?**
O Power BI só tem as tabelas do schema `dw_campo_real`. Nenhuma tabela de origem foi importada.
