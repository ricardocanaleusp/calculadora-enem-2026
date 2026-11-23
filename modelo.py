"""Núcleo matemático da calculadora ENEM 2026.

A estimativa pública é uma referência por contagem de acertos, baseada na
inversão interpolada de pontos históricos de 2012–2025. NÃO é TRI por item.
A função tri_3pl/eap_3pl existe para a futura integração de parâmetros
calibrados, mas NÃO é acionada automaticamente na estimativa pública.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import median

AREAS = {
    "LC": ("Linguagens e Códigos", 1, 45, 1),
    "CH": ("Ciências Humanas", 46, 90, 1),
    "CN": ("Ciências da Natureza", 91, 135, 2),
    "MT": ("Matemática", 136, 180, 2),
}

CADERNOS = {
    1: {"Azul": 1, "Amarelo": 2, "Branco": 3, "Verde": 4},
    2: {"Amarelo": 5, "Cinza": 6, "Azul": 7, "Verde": 8},
}

# Correspondencia oficial do item de Matematica anulado em 2026.
# Aplicacao regular, segundo dia. Um unico item ocupa posicoes distintas.
ANULADA_MT_2026 = {"Azul": 159, "Amarelo": 153, "Cinza": 164, "Verde": 158}


def questao_anulada_mt(cor: str) -> int:
    if cor not in ANULADA_MT_2026:
        raise ValueError("Cor do segundo dia invalida")
    return ANULADA_MT_2026[cor]


def acertos_validos_mt(questoes: set[int], cor: str) -> tuple[int, bool]:
    """Retorna numero de acertos validos e se anulada havia sido selecionada."""
    anulada = questao_anulada_mt(cor)
    return len(questoes - {anulada}), anulada in questoes


def converter_44_para_referencia_45(k: int) -> float:
    """Equivalencia proporcional exploratoria, NAO recalibracao TRI."""
    if type(k) is not int or not 0 <= k <= 44:
        raise ValueError("Matematica: acertos validos devem estar entre 0 e 44")
    return (45.0 / 44.0) * k


FONTE_INEP = "https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/enem/provas-e-gabaritos/2026"


@dataclass(frozen=True)
class Estimativa:
    central: float
    faixa_baixa: float
    faixa_alta: float
    extrapolacoes: int
    n_anos: int


def carregar_historico(arquivo: str | Path) -> dict[str, list[dict]]:
    d: dict[str, list[dict]] = {a: [] for a in AREAS}
    with open(arquivo, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            ano = int(r["ano"])
            area = r["area"].upper().strip()
            notas = [float(x) for x in r["notas"].split("|")]
            acertos = [int(x) for x in r["acertos"].split("|")]
            if area not in AREAS or not 2009 <= ano <= 2025:
                raise ValueError(f"Ano/área inválidos: {ano}/{area}")
            if (len(notas) < 2 or len(notas) != len(acertos)
                or not all(x < y for x, y in zip(notas, notas[1:]))
                or not all(x < y for x, y in zip(acertos, acertos[1:]))
                or any(q < 0 or q > 45 for q in acertos)):
                raise ValueError(f"Âncoras inválidas: {area}/{ano}")
            if any(v["ano"] == ano for v in d[area]):
                raise ValueError(f"Ano duplicado: {area}/{ano}")
            d[area].append({"ano": ano, "notas": notas,
                            "acertos": acertos, "fonte": r["fonte"]})
    for area in d:
        d[area].sort(key=lambda v: v["ano"])
    return d


def estimar_por_ano(k: float, notas: list[float], acertos: list[int]) -> tuple[float,bool]:
    if not isinstance(k, (int, float)) or not math.isfinite(k) or not 0 <= k <= 45:
        raise ValueError("Acertos precisam ser inteiros entre 0 e 45")
    # Inversão linear entre âncoras, com extrapolação SE E SOMENTE SE
    # não há âncoras para essa contagem; muito incerta nos extremos.
    if k < acertos[0]:
        j = 0
        extrapola = True
    elif k > acertos[-1]:
        j = len(acertos) - 2
        extrapola = True
    else:
        j = next((i for i in range(len(acertos)-1)
                  if acertos[i] <= k <= acertos[i+1]), len(acertos)-2)
        extrapola = False
    valor = notas[j] + ((k - acertos[j]) *
                        (notas[j+1] - notas[j]) /
                        (acertos[j+1] - acertos[j]))
    # Barreiras computacionais, não máximos/mínimos oficiais.
    return max(0.0, min(1000.0, valor)), extrapola


def quantil_ordenado(valores: list[float], p: float) -> float:
    if not valores or not 0 <= p <= 1:
        raise ValueError("Quantil inválido")
    s = sorted(valores)
    pos = (len(s)-1)*p
    inferior = math.floor(pos)
    superior = math.ceil(pos)
    return s[inferior] + (pos-inferior)*(s[superior]-s[inferior])


def estimar_historico(k: float, area: str, base: dict[str,list[dict]]) -> Estimativa:
    if area not in AREAS:
        raise ValueError("Área inválida")
    regs = base[area]
    if len(regs) < 2:
        raise ValueError("Necessárias duas ou mais edições para estimativa")
    cenarios = [estimar_por_ano(k, r["notas"], r["acertos"]) for r in regs]
    v = [r[0] for r in cenarios]
    return Estimativa(central=median(v), faixa_baixa=quantil_ordenado(v,.1),
                     faixa_alta=quantil_ordenado(v,.9),
                     extrapolacoes=sum(ex for _,ex in cenarios), n_anos=len(regs))


def interpretar_numeros(texto: str, inicio: int, fim: int) -> set[int]:
    resultado: set[int] = set()
    for p in texto.replace(';',',').split(','):
        p = p.strip()
        if not p:
            continue
        if '-' in p:
            partes = p.split('-')
            if len(partes) != 2 or not all(x.strip().isdigit() for x in partes):
                raise ValueError("Intervalo inválido: " + p)
            a,b = (int(x) for x in partes)
            if a > b:
                raise ValueError("Intervalo invertido: " + p)
            numeros = range(a,b+1)
        elif p.isdigit():
            numeros = [int(p)]
        else:
            raise ValueError("Número inválido: " + p)
        for n in numeros:
            if not inicio <= n <= fim:
                raise ValueError(f"Questão {n} fora da área ({inicio}–{fim})")
            if n in resultado:
                raise ValueError(f"Questão repetida: {n}")
            resultado.add(n)
    return resultado


def tri_3pl(theta: float, a: float, b: float, c: float, d: float=1.0) -> float:
    if not (all(math.isfinite(x) for x in (theta,a,b,c,d))
            and a>0 and 0<=c<1 and d>0):
        raise ValueError("Parâmetros TRI inválidos")
    z=d*a*(theta-b)
    L=1/(1+math.exp(-z)) if z>=0 else math.exp(z)/(1+math.exp(z))
    return c+(1-c)*L


def eap_3pl(respostas: list[int], parametros: list[tuple[float,float,float]], d: float=1.) -> float:
    """EAP em métrica latente; não produz nota do Inep sem linking válido."""
    if len(respostas)!=len(parametros) or not respostas or any(u not in (0,1) for u in respostas):
        raise ValueError("Respostas e parâmetros incompatíveis")
    grade=[-5+i*.025 for i in range(401)]
    logs=[]
    for theta in grade:
        soma=-theta*theta/2  # priori normal padrão, ilustrativa
        for u,(a,b,c) in zip(respostas,parametros):
            p=tri_3pl(theta,a,b,c,d)
            p=min(1-1e-12,max(1e-12,p))
            soma+=math.log(p) if u else math.log1p(-p)
        logs.append(soma)
    ref=max(logs)
    w=[math.exp(x-ref) for x in logs]
    return sum(x*y for x,y in zip(grade,w))/sum(w)
