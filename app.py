"""Calculadora ENEM 2026 – quatro áreas. Execute: streamlit run app.py"""
from pathlib import Path
import csv
import io
import streamlit as st
from modelo import AREAS, CADERNOS, FONTE_INEP, carregar_historico, estimar_historico, interpretar_numeros, questao_anulada_mt, acertos_validos_mt, converter_44_para_referencia_45

st.set_page_config(page_title="Calculadora ENEM 2026 – quatro áreas", page_icon="📊",layout="wide")

@st.cache_data

def base_dados():
    return carregar_historico(Path(__file__).with_name("historico_2012_2025.csv"))

base=base_dados()
st.title("Calculadora ENEM 2026")
st.caption("Primeiro e segundo dias · Linguagens · Humanas · Natureza · Matemática")
st.info("**Previsão exploratória por acertos.** Utiliza referências históricas de 2012 a 2025; "
        "os parâmetros psicométricos de cada item de 2026 ainda não foram calibrados neste projeto. "
        "As estimativas e faixas não substituem as notas oficiais do Inep.")

st.subheader("1. Identifique os cadernos")
c1,c2,c3=st.columns(3)
with c1:
    cor1=st.selectbox("Primeiro dia (LC e CH)", list(CADERNOS[1]), index=0)
    st.caption(f"Caderno {CADERNOS[1][cor1]} · {cor1}")
with c2:
    cor2=st.selectbox("Segundo dia (CN e MT)",list(CADERNOS[2]),index=0)
    st.caption(f"Caderno {CADERNOS[2][cor2]} · {cor2}")
with c3:
    lingua=st.selectbox("Língua estrangeira",["Inglês","Espanhol"])

st.subheader("2. Informe quais questões acertou")
q_anulada = questao_anulada_mt(cor2)
st.warning(f"**Matemática: questão {q_anulada} anulada no caderno {cor2}.** "
           "O item está excluído para todos, independentemente da resposta. "
           "São 44 itens válidos em Matemática, e não 45 acertos possíveis.")
st.caption("Marque as questões que **acertou** conforme a numeração do seu caderno. "
           "Também é possível digitar os números e intervalos, como 1-10, 13, 21. "
           "As questões não marcadas contam como não acertadas somente após sua confirmação.")

if "ultimo_resultado" not in st.session_state:
    st.session_state.ultimo_resultado=None

respostas={}
with st.form("cartao_resposta"):
    for area,(nome,ini,fim,dia) in AREAS.items():
        with st.expander(f"{nome} · questões {ini} a {fim}",expanded=True):
            st.caption("Selecione as questões acertadas ou use a lista de números abaixo.")
            grid=[]
            for i in range(0,45,9):
                colunas=st.columns(9)
                for j,col in enumerate(colunas):
                    q=ini+i+j
                    with col:
                        if area == "MT" and q == q_anulada:
                            st.markdown(f"~~{q}~~ 🚫")
                        else:
                            grid.append(q if st.checkbox(str(q),key=f"q_{area}_{q}") else None)
            entrada=st.text_input(f"Lista adicional de acertos em {nome}",key=f"entrada_{area}",
                                  placeholder=f"Exemplo: {ini}-{ini+4}, {ini+8}")
            respostas[area]=([q for q in grid if q is not None],entrada)
    confirmado=st.checkbox("Conferi meus acertos nas quatro áreas. Todas as demais questões não foram acertadas.")
    enviar=st.form_submit_button("Calcular minhas quatro notas possíveis",type="primary",use_container_width=True)

if enviar:
    if not confirmado:
        st.warning("Confirme a conferência das quatro áreas antes do cálculo.")
    else:
        try:
            contagens={}
            digitou_anulada=False
            for area,(_,ini,fim,_) in AREAS.items():
                selecionadas,texto=respostas[area]
                digitadas=interpretar_numeros(texto,ini,fim)
                conjunto=set(selecionadas) | digitadas
                if area == "MT":
                    contagens[area], digitou_anulada = acertos_validos_mt(conjunto, cor2)
                else:
                    contagens[area]=len(conjunto)
            st.session_state.ultimo_resultado={
                "contagens":contagens,"cor1":cor1,"cor2":cor2,"lingua":lingua,
                "digitou_anulada":digitou_anulada,
            }
        except ValueError as e:
            st.error(str(e))

result=st.session_state.ultimo_resultado
if result:
    st.divider()
    st.subheader("3. Resultados preliminares")
    if result.get("digitou_anulada"):
        st.info("A questão anulada de Matemática foi informada na lista, "
                "mas foi retirada automaticamente da contagem de acertos válidos.")
    st.caption(f"No caderno {result['cor2']} do segundo dia, a questão "
               f"{questao_anulada_mt(result['cor2'])} foi anulada. "
               "Matemática: 44 questões válidas.")
    rows=[]
    cols=st.columns(4)
    for col,(area,(nome,_,_,_)) in zip(cols,AREAS.items()):
        k=result["contagens"][area]
        # O modelo historico utiliza pontos de referencia de provas com 45 itens.
        # Em MT, aplica-se uma conversao proporcional exploratoria de 44 para 45.
        k_referencia = converter_44_para_referencia_45(k) if area == "MT" else k
        e=estimar_historico(k_referencia,area,base)
        with col:
            st.metric(nome,f"{e.central:.0f} pontos",f"{k}/{44 if area == 'MT' else 45} acertos válidos",delta_color="off")
            if area == "MT":
                st.caption("Nota provisória com equivalência 45 × acertos válidos / 44. "
                           "Não equivale à recalibração TRI oficial.")
            st.caption(f"Cenários históricos: {e.faixa_baixa:.0f}–{e.faixa_alta:.0f}")
            if e.extrapolacoes:
                st.caption(f"⚠️ Extrapolação em {e.extrapolacoes}/{e.n_anos} edições")
        rows.append({"Área":nome,"Acertos":k,"Nota preliminar":round(e.central),
                     "Referência inferior":round(e.faixa_baixa),"Referência superior":round(e.faixa_alta),
                     "Edições extrapoladas":e.extrapolacoes})
    st.caption("O item anulado foi excluído. Para Matemática, as referências históricas "
               "de 45 questões foram ajustadas proporcionalmente para 44 válidas; "
               "essa hipótese requer validação. "
               "As faixas descrevem a variação dos cenários históricos interpolados. "
               "Não representam intervalos preditivos validados nem incorporam a variação "
               "de nota entre participantes com o mesmo número de acertos.")
    c1,c2=st.columns(2)
    with c1:
        redacao=st.number_input("Nota de redação (opcional)",min_value=0,max_value=1000,value=0,step=20,
                                help="Deixe a opção desmarcada se ainda não souber a nota.")
        incluir_redacao=st.checkbox("Incluir redação na média simples")
    notas=[r["Nota preliminar"] for r in rows]
    with c2:
        media=sum(notas + ([redacao] if incluir_redacao else []))/(5 if incluir_redacao else 4)
        st.metric("Média preliminar das áreas selecionadas",f"{media:.1f} pontos")
        st.caption("A média das quatro áreas é diferente da média das cinco provas.")
    saida=io.StringIO()
    escritor=csv.DictWriter(saida,fieldnames=list(rows[0]))
    escritor.writeheader();escritor.writerows(rows)
    st.download_button("Baixar resultados em CSV",saida.getvalue().encode("utf-8-sig"),
                       file_name="enem_2026_resultados_preliminares.csv",mime="text/csv")

with st.expander("Metodologia, fontes e limites",expanded=False):
    st.markdown("""**Modelo efetivamente usado:** tabela anual de medianas de acertos por faixa de nota,
    derivada de análises secundárias dos microdados do Inep (2012–2025). Para cada ano,
    invertemos por interpolação linear os pontos publicados e obtemos uma nota correspondente
    ao total de acertos. A nota central exibida é a mediana das 14 estimativas anuais.
    Os quantis de 10% e 90% desses cenários geram apenas uma faixa descritiva entre anos.

    A inversão de mediana de acertos condicionada à nota não equivale rigorosamente à mediana
    da nota condicionada aos acertos. A extrapolação nas extremidades depende de hipóteses
    adicionais e possui confiabilidade especialmente baixa. O modelo não passou por
    validação retrospectiva de previsões de 2026 e não utiliza o padrão psicométrico
    individual das questões. A comparação com um 3PL bayesiano por item permanece prevista,
    assim como a auditoria e integração de 2009–2011.

    **Item anulado em Matemática:** a questão 159 (azul), 153 (amarelo),
    164 (cinza) ou 158 (verde) representa um único item excluído para todos.
    O aplicativo impede sua seleção na grade e ignora sua indicação manual.
    A estimativa histórica de Matemática usa o número de acertos válidos multiplicado
    por 45/44 para aproximar as referências históricas de 45 questões; trata-se de
    um ajuste exploratório, não da correção oficial pela TRI. A escala pode depender
    dos parâmetros dos 44 itens efetivamente usados e da equalização.

    A seleção da cor e do idioma organiza o preenchimento, mas não modifica
    a previsão para uma mesma quantidade de acertos válidos. Não há gabarito
    incorporado à correção; o participante informa seus acertos após conferir a prova.
    """)
    st.markdown("**Referências históricas secundárias:** [Linguagens](https://profrafaelteixeira.com.br/raio-x-da-tri-do-enem/linguagens/), "
                "[Humanas](https://profrafaelteixeira.com.br/raio-x-da-tri-do-enem/ciencias-humanas/), "
                "[Natureza](https://profrafaelteixeira.com.br/raio-x-da-tri-do-enem/ciencias-da-natureza/) e "
                "[Matemática](https://profrafaelteixeira.com.br/raio-x-da-tri-do-enem/matematica/).")
    st.markdown(f"[**Provas e gabaritos oficiais do Inep (2026)**]({FONTE_INEP})")
    st.caption("Projeto experimental independente, sem vínculo institucional com o Inep ou a TriEduc.")
