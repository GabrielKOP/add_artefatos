#!/usr/bin/env python3
"""
Interface de desktop do simulador da fila da catraca do RU.

Usa as funções do analise_catraca.py (medir, simular_cenarios, validar...). Com os
mesmos parâmetros e a mesma semente, os números são os do relatorio.txt.

Instalação:  python -m pip install PySide6 matplotlib
Uso:         python simulador_gui.py                (abre com as sessões de exemplo)
             python simulador_gui.py A.csv B.csv C.csv
"""
import math
import os
import random
import statistics
import sys
from datetime import timedelta

import analise_catraca as ac

try:
    from PySide6.QtCore import QElapsedTimer, QPoint, QPointF, QRectF, Qt, QThread, QTimer, Signal
    from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QPainter, QPainterPath, QPen
    from PySide6.QtWidgets import (
        QApplication, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame,
        QGridLayout, QHBoxLayout, QHeaderView, QLabel, QMainWindow, QMessageBox, QProgressBar,
        QPushButton, QScrollArea, QSizePolicy, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget,
        QToolTip, QVBoxLayout, QWidget,
    )
    import matplotlib
    matplotlib.use('QtAgg')
    from matplotlib import font_manager
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
    from matplotlib.ticker import FuncFormatter, MaxNLocator
except ImportError as e:
    sys.exit(f'Falta uma biblioteca ({e.name}). Instale com:  python -m pip install PySide6 matplotlib')

PASTA = os.path.dirname(os.path.abspath(__file__))

# Sessões que já vêm na pasta artefatos/, com os parâmetros usados no LEIA-ME de lá.
EXEMPLOS = [
    ('17/11 · almoço inteiro', 'artefatos/analise_almoco_inteiro/c17_full_desist.csv', 4.94, 80,
     'Resultado principal do relatório: 11:31–13:15, fila inicial 42 e 48 desistências não vistas '
     'acrescentadas entre 12:31 e 13:15. μ = 4,94 /min e K = 80, como no LEIA-ME.'),
    ('17/11 · primeira hora', 'artefatos/analise_primeira_hora/c17_1h_semcron.csv', 6.18, 80,
     'Só dados observados, 11:31–12:31, fila inicial 42. μ = 6,18 /min e K = 80, como no LEIA-ME.'),
]

# Nome do cenário no analise_catraca.py -> chave usada para cor e seleção
CHAVES = {'1 catraca': 'base', '1 cat. sem desist.': 'semdes', '2ª só no pico': 'pico2',
          '2 a hora toda': 'toda2', 'Personalizado': 'pers'}
NOMES_LONGOS = {'base': '1 catraca', 'semdes': '1 catraca sem desistência', 'pico2': '2ª catraca só no pico',
                'toda2': '2 catracas a hora toda', 'pers': 'Personalizado'}

TEMAS = {
    'claro': dict(
        bg='#eef1f4', surface='#ffffff', surface2='#f5f7f9', ink='#14212b', muted='#5c6b77', line='#dbe2e8',
        accent='#2a78d6', accent_hover='#256abf', accent_ink='#ffffff', pico='#f9e4e1',
        espera='#7b8a96', cat='#b8500a', ok='#2b7a4b', alert='#c0392b', barras='#0a6a8a',
        series={'base': '#2a78d6', 'semdes': '#8a949c', 'pico2': '#1baf7a', 'toda2': '#eb6834', 'pers': '#6250d6'},
    ),
    'escuro': dict(
        bg='#0f161c', surface='#17212a', surface2='#1e2a34', ink='#e8eef2', muted='#93a3af', line='#2a3945',
        accent='#3987e5', accent_hover='#5598e7', accent_ink='#ffffff', pico='#2f2228',
        espera='#8b9aa6', cat='#f0985a', ok='#5ccf8a', alert='#ff7a6b', barras='#4cb8d9',
        series={'base': '#3987e5', 'semdes': '#8b949c', 'pico2': '#199e70', 'toda2': '#d95926', 'pers': '#9085e9'},
    ),
}

br = ac.br


def pct(x):
    return br(x * 100, 0) + '%'


# =================================================================== cálculo (fora da interface)
class Cancelado(Exception):
    pass


def calcular(c, progresso=None):
    """Roda a simulação inteira com a configuração `c` montada pela janela.
    Mesma sequência do analisar() do analise_catraca.py: verificação, passo seguro, cenários, validação."""
    pico, mu = c['pico'], c['mu']
    out = {'cfg': c, 'avisos': []}
    lams = ac.lams_por_minuto(pico, c['lam_cal'], c['lam_pic'], c['lam_med'])
    out['lams'] = lams
    passo = c['passo']

    if c['lam_cal'] is not None and c['lam_cal'] > 0 and ac.formulas(c['lam_cal'], mu)['estavel']:
        pv = ac.passo_seguro([c['lam_cal']], mu, 1, 0.0, c['K'], passo)
        out['verif'] = ac.verificar(c['lam_cal'], mu, c['K'], c['seed'], pv)

    cen = [x for x in ac.cenarios_padrao(pico, c['theta']) if CHAVES[x[0]] == 'base' or CHAVES[x[0]] in c['sel']]
    if 'pers' in c['sel']:
        cc, cp, desist = c['pers']
        cen.append(('Personalizado', [cp if p else cc for p in pico], c['theta'] if desist else 0.0))
    cmax = max(max(cs) for _, cs, _ in cen)
    novo = ac.passo_seguro(lams, mu, max(2, cmax), c['theta'], c['K'], passo)
    if novo != passo:
        out['avisos'].append(f'Passo reduzido de {br(passo, 1)} s para {br(novo, 1)} s: com μ = {br(mu)} /min '
                             'o passo maior daria chances somando mais de 1.')
        passo = novo
    out['passo'] = passo

    res = ac.simular_cenarios(cen, lams, mu, c['n0'], c['K'], c['seed'], passo, c['reps'], c['lam_med'], progresso)
    for nome, r in res.items():
        r['chave'] = CHAVES[nome]
        cols = list(zip(*r['hs']))
        r['media'] = [sum(col) / len(col) for col in cols]
        if nome == '1 catraca':
            r['p05'] = [ac.percentil(col, .05) for col in cols]
            r['p95'] = [ac.percentil(col, .95) for col in cols]
    out['res'] = res
    if c['d'] and c['d']['fila']:
        out['valid'] = ac.validar(c['d']['fila'], res['1 catraca']['hs'], passo)
    return out


def rastrear(hist, lams, mu, cs, n0, K, seed, passo, theta):
    """Refaz os sorteios de uma réplica (mesmo random.Random(seed) do simular) para saber o que
    aconteceu em cada passo: 0 nada, 1 chegada, 2 passou na catraca, 3 desistiu, 4 chegou com a fila cheia."""
    rng, n, T = random.Random(seed), n0, len(lams)
    s = mu * passo / 60
    ev = bytearray(len(hist))
    for i, novo in enumerate(hist):
        m = min(int(i * passo / 60), T - 1)
        a = lams[m] * passo / 60
        d = max(n - cs[m], 0) * theta * passo / 60
        u = rng.random()
        if u < a:
            e = 1 if n < K else 4
        elif u < a + min(n, cs[m]) * s:
            e = 2
        elif u < a + min(n, cs[m]) * s + d:
            e = 3
        else:
            e = 0
        n = novo
        ev[i] = e
    return ev


class Rodada(QThread):
    progresso = Signal(int)
    pronto = Signal(object)
    falhou = Signal(str)

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self._ultimo = -1

    def _prog(self, feitas, total):
        if self.isInterruptionRequested():
            raise Cancelado()
        p = int(100 * feitas / total)
        if p != self._ultimo:
            self._ultimo = p
            self.progresso.emit(p)

    def run(self):
        try:
            self.pronto.emit(calcular(self.cfg, self._prog))
        except Cancelado:
            pass
        except SystemExit as e:  # simular() encerra o script quando o passo é grande demais
            self.falhou.emit(str(e))
        except Exception as e:  # noqa: BLE001 — mostra qualquer erro na janela
            self.falhou.emit(f'{type(e).__name__}: {e}')


# =================================================================== estilo
def qss(t):
    return f"""
    * {{ font-family: 'Segoe UI Variable Text', 'Segoe UI', 'Inter', sans-serif; font-size: 10pt; color: {t['ink']}; }}
    QMainWindow, QWidget#raiz {{ background: {t['bg']}; }}
    QScrollArea {{ background: transparent; border: none; }}
    QWidget#miolo {{ background: transparent; }}
    QFrame#card {{ background: {t['surface']}; border: 1px solid {t['line']}; border-radius: 12px; }}
    QFrame#cartao {{ background: {t['surface']}; border: 1px solid {t['line']}; border-radius: 12px; }}
    QFrame#cartao[sel="true"] {{ border: 2px solid {t['ink']}; }}
    QFrame#cartao:hover {{ border-color: {t['muted']}; }}
    QLabel {{ background: transparent; }}
    QLabel#titulo {{ font-size: 17pt; font-weight: 700; }}
    QLabel#h2 {{ font-size: 11.5pt; font-weight: 700; }}
    QLabel#h3 {{ font-size: 10pt; font-weight: 700; color: {t['muted']}; }}
    QLabel[papel="dica"] {{ color: {t['muted']}; font-size: 9pt; }}
    QLabel[papel="medido"] {{ color: {t['muted']}; font-size: 8.5pt; }}
    QLabel[papel="rotulo"] {{ color: {t['muted']}; font-size: 8.5pt; font-weight: 600; letter-spacing: 1px; }}
    QLabel[papel="campo"] {{ color: {t['muted']}; font-size: 9pt; font-weight: 600; }}
    QLabel[papel="grande"] {{ font-size: 24pt; font-weight: 700; }}
    QLabel[papel="conclusao"] {{ font-size: 13pt; font-weight: 600; }}
    QLabel[papel="num"] {{ font-size: 17pt; font-weight: 700; }}
    QLabel[papel="erro"] {{ color: {t['alert']}; font-size: 9pt; }}
    QLabel[papel="bom"] {{ color: {t['ok']}; font-weight: 600; }}
    QLabel[papel="ruim"] {{ color: {t['alert']}; font-weight: 600; }}
    QLabel[papel="selo-pico"] {{ background: {t['pico']}; color: {t['alert']}; border-radius: 10px; padding: 3px 10px; font-weight: 700; }}
    QLabel[papel="selo-calma"] {{ background: {t['surface2']}; color: {t['muted']}; border: 1px solid {t['line']}; border-radius: 10px; padding: 3px 10px; font-weight: 700; }}
    QSpinBox, QDoubleSpinBox, QComboBox {{
        background: {t['surface2']}; border: 1px solid {t['line']}; border-radius: 8px;
        padding: 5px 8px; min-height: 22px; selection-background-color: {t['accent']}; selection-color: #fff; }}
    QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border: 1px solid {t['accent']}; }}
    QSpinBox[editado="true"], QDoubleSpinBox[editado="true"] {{ border: 1px solid {t['cat']}; }}
    QSpinBox:disabled, QDoubleSpinBox:disabled {{ color: {t['muted']}; }}
    QComboBox::drop-down {{ border: none; width: 24px; }}
    QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width: 0px; border: none; }}
    QComboBox QAbstractItemView {{ background: {t['surface']}; border: 1px solid {t['line']}; padding: 4px;
        selection-background-color: {t['accent']}; selection-color: #fff; outline: none; }}
    QPushButton {{ background: {t['surface']}; border: 1px solid {t['line']}; border-radius: 8px;
        padding: 7px 14px; font-weight: 600; }}
    QPushButton:hover {{ border-color: {t['accent']}; }}
    QPushButton:disabled {{ color: {t['muted']}; border-color: {t['line']}; }}
    QPushButton[papel="primario"] {{ background: {t['accent']}; color: {t['accent_ink']}; border: none; padding: 9px 16px; }}
    QPushButton[papel="primario"]:hover {{ background: {t['accent_hover']}; }}
    QPushButton[papel="primario"]:disabled {{ background: {t['line']}; color: {t['muted']}; }}
    QPushButton[papel="seg"] {{ border-radius: 7px; padding: 5px 11px; background: {t['surface2']}; }}
    QPushButton[papel="seg"]:checked {{ background: {t['ink']}; color: {t['bg']}; border-color: {t['ink']}; }}
    QPushButton[papel="fino"] {{ background: transparent; border: none; color: {t['accent']}; padding: 4px 0; text-align: left; }}
    QPushButton[papel="fino"]:hover {{ text-decoration: underline; }}
    QCheckBox {{ spacing: 8px; }}
    QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px; border: 1px solid {t['muted']}; background: {t['surface2']}; }}
    QCheckBox::indicator:checked {{ background: {t['accent']}; border-color: {t['accent']}; }}
    QCheckBox::indicator:disabled {{ background: {t['line']}; border-color: {t['line']}; }}
    QCheckBox::indicator:checked:disabled {{ background: {t['muted']}; border-color: {t['muted']}; }}
    QTabWidget::pane {{ border: none; }}
    QTabBar::tab {{ background: transparent; color: {t['muted']}; padding: 8px 18px; margin-right: 6px;
        border-radius: 9px; font-weight: 600; border: 1px solid transparent; }}
    QTabBar::tab:selected {{ background: {t['surface']}; color: {t['ink']}; border: 1px solid {t['line']}; }}
    QTabBar::tab:hover:!selected {{ color: {t['ink']}; }}
    QProgressBar {{ background: {t['surface2']}; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }}
    QProgressBar::chunk {{ background: {t['accent']}; border-radius: 3px; }}
    QTableWidget {{ background: {t['surface']}; border: none; gridline-color: transparent;
        alternate-background-color: {t['surface2']}; selection-background-color: {t['surface2']}; selection-color: {t['ink']}; }}
    QTableWidget::item {{ padding: 4px 8px; }}
    QHeaderView::section {{ background: {t['surface']}; color: {t['muted']}; border: none;
        border-bottom: 1px solid {t['line']}; padding: 6px 8px; font-weight: 600; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {t['line']}; border-radius: 4px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {t['muted']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QToolTip {{ background: {t['surface']}; color: {t['ink']}; border: 1px solid {t['line']}; padding: 6px; }}
    """


def rotulo(texto, papel=None, nome=None, quebra=False):
    lb = QLabel(texto)
    if papel:
        lb.setProperty('papel', papel)
    if nome:
        lb.setObjectName(nome)
    lb.setWordWrap(quebra)
    return lb


def card():
    f = QFrame()
    f.setObjectName('card')
    lay = QVBoxLayout(f)
    lay.setContentsMargins(16, 14, 16, 16)
    lay.setSpacing(8)
    return f, lay


def repolir(w):
    w.style().unpolish(w)
    w.style().polish(w)


# =================================================================== animação da fila
class Aluno:
    __slots__ = ('x', 'y', 'tx', 'ty', 'a', 'ta', 'estado')

    def __init__(self, x, y, a=1.0):
        self.x = self.tx = x
        self.y = self.ty = y
        self.a, self.ta = a, 1.0
        self.estado = 'espera'


class Palco(QWidget):
    """Desenha uma réplica da simulação: alunos esperando em serpentina e as catracas à direita."""
    mudou = Signal(int)
    terminou = Signal()
    ESP = 15         # espaço entre alunos na fila
    CAT_W, CAT_H, CAT_GAP = 92, 34, 10

    def __init__(self, tema):
        super().__init__()
        self.t = tema
        self.hist = None
        self.rodando = False
        self.vel = 30
        self.k = -1
        self.tsim = 0.0
        self.fila, self.cats, self.saindo = [], [], []
        self.aviso_k = 0.0
        self.rng = random.Random(7)
        self.relogio = QElapsedTimer()
        self.relogio.start()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._quadro)
        self.timer.start(16)
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # ---- dados
    def carregar(self, hist, ev, cs, n0, passo, K):
        self.hist, self.ev, self.cs, self.n0, self.passo, self.K = hist, ev, cs, n0, passo, K
        self.N, self.T = len(hist), len(cs)
        self.cmax = max(cs)
        self.acum = {e: [] for e in (1, 2, 3, 4)}
        cont = {e: 0 for e in (1, 2, 3, 4)}
        for e in ev:
            if e:
                cont[e] += 1
            for x in (1, 2, 3, 4):
                self.acum[x].append(cont[x])
        self._geometria()
        self.ir_para(-1)

    def catracas_no_passo(self, k):
        return self.cs[min(int(max(k, 0) * self.passo / 60), self.T - 1)]

    def contagem(self, tipo):
        return self.acum[tipo][self.k] if self.k >= 0 else 0

    # ---- geometria
    def _geometria(self):
        if self.hist is None:
            return
        w = max(self.width(), 300)
        self.cat_x = w - self.CAT_W - 70
        self.topo = 18
        self.q_dir = self.cat_x - 26
        self.q_esq = 22
        self.cap = max(4, int((self.q_dir - self.q_esq) / self.ESP) + 1)
        maior = max(self.K, self.n0, max(self.hist))
        self.linhas = min(14, math.ceil(maior / self.cap))
        y0 = self.topo + self.CAT_H / 2
        alt_fila = y0 + (self.linhas - 1) * self.ESP + 30
        alt_cat = self.topo + self.cmax * (self.CAT_H + self.CAT_GAP) + 20
        self.setFixedHeight(int(max(alt_fila, alt_cat, 150)))

    def pos_fila(self, j):
        j = min(j, self.cap * self.linhas - 1)
        r, c = divmod(j, self.cap)
        x = self.q_dir - c * self.ESP if r % 2 == 0 else self.q_esq + c * self.ESP
        return x, self.topo + self.CAT_H / 2 + r * self.ESP

    def pos_cat(self, i):
        return self.cat_x + 16, self.topo + i * (self.CAT_H + self.CAT_GAP) + self.CAT_H / 2

    def resizeEvent(self, ev):
        self._geometria()
        self._alvos(instantaneo=True)
        super().resizeEvent(ev)

    # ---- estado
    def ir_para(self, k):
        if self.hist is None:
            return
        self.k = max(-1, min(k, self.N - 1))
        self.tsim = (self.k + 1) * self.passo
        n = self.n0 if self.k < 0 else self.hist[self.k]
        c = self.catracas_no_passo(self.k)
        self.fila, self.saindo = [], []
        self.cats = [None] * self.cmax
        for i in range(min(n, c)):
            self.cats[i] = Aluno(*self.pos_cat(i))
            self.cats[i].estado = 'catraca'
        for j in range(n - min(n, c)):
            self.fila.append(Aluno(*self.pos_fila(j)))
        self._alvos(instantaneo=True)
        self.mudou.emit(self.k)
        self.update()

    def _ocupar(self, c):
        for i in range(c):
            if self.cats[i] is None and self.fila:
                al = self.fila.pop(0)
                al.estado = 'catraca'
                self.cats[i] = al

    def _alvos(self, instantaneo=False):
        if self.hist is None:
            return
        for j, al in enumerate(self.fila):
            al.tx, al.ty = self.pos_fila(j)
        for i, al in enumerate(self.cats):
            if al:
                al.tx, al.ty = self.pos_cat(i)
        if instantaneo:
            for al in self.fila + [a for a in self.cats if a]:
                al.x, al.y = al.tx, al.ty

    def _aplicar(self, i):
        e = self.ev[i]
        c = self.catracas_no_passo(i)
        if e == 1:
            x, y = self.pos_fila(len(self.fila))
            self.fila.append(Aluno(x - 20, y, a=0.0))
        elif e == 4:
            self.aviso_k = 1.0
        elif e == 2:
            ocup = [j for j, al in enumerate(self.cats) if al]
            if ocup:
                j = self.rng.choice(ocup)
                al = self.cats[j]
                self.cats[j] = None
                al.estado, al.tx, al.ta = 'passou', self.width() + 30, 0.0
                self.saindo.append(al)
        elif e == 3:
            if self.fila:
                al = self.fila.pop(self.rng.randrange(len(self.fila)))
            else:  # fechou uma catraca com gente ainda nela
                ocup = [j for j, a in enumerate(self.cats) if a and j >= c] or [j for j, a in enumerate(self.cats) if a]
                if not ocup:
                    return
                j = ocup[0]
                al, self.cats[j] = self.cats[j], None
            al.estado, al.ty, al.ta = 'desistiu', al.y - 22, 0.0
            self.saindo.append(al)
        self._ocupar(c)

    # ---- reprodução
    def tocar(self, sim):
        if self.hist is None:
            return
        if sim and self.k >= self.N - 1:
            self.ir_para(-1)
        self.rodando = sim

    def _quadro(self):
        dt = min(self.relogio.restart() / 1000, 0.1)
        if self.hist is None:
            return
        if self.rodando:
            self.tsim += dt * self.vel
            alvo = min(int(self.tsim / self.passo) - 1, self.N - 1)
            if alvo - self.k > 400:
                self.ir_para(alvo)
            elif alvo > self.k:
                for i in range(self.k + 1, alvo + 1):
                    self._aplicar(i)
                self.k = alvo
                self._alvos()
                self.mudou.emit(self.k)
            if self.k >= self.N - 1:
                self.rodando = False
                self.terminou.emit()
        f = 1 - math.exp(-dt * 11)
        fa = 1 - math.exp(-dt * 5)
        vivos = []
        for al in self.fila + [a for a in self.cats if a] + self.saindo:
            al.x += (al.tx - al.x) * f
            al.y += (al.ty - al.y) * f
            al.a += (al.ta - al.a) * (fa if al.estado in ('passou', 'desistiu') else f)
        for al in self.saindo:
            if al.a > 0.03:
                vivos.append(al)
        self.saindo = vivos
        self.aviso_k = max(0.0, self.aviso_k - dt * 1.5)
        self.update()

    # ---- desenho
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = self.t
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t['surface2']))
        p.drawRoundedRect(QRectF(self.rect()), 10, 10)
        if self.hist is None:
            p.setPen(QColor(t['muted']))
            p.drawText(self.rect(), Qt.AlignCenter, 'Rode a simulação para ver a fila.')
            return
        c = self.catracas_no_passo(self.k)
        fonte = QFont(self.font())
        fonte.setPointSizeF(8.5)
        p.setFont(fonte)
        # catracas
        for i in range(self.cmax):
            y = self.topo + i * (self.CAT_H + self.CAT_GAP)
            r = QRectF(self.cat_x, y, self.CAT_W, self.CAT_H)
            aberta = i < c
            pen = QPen(QColor(t['ink'] if aberta else t['line']), 1.4)
            if not aberta:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.setBrush(QColor(t['surface']))
            p.drawRoundedRect(r, 7, 7)
            p.setPen(QColor(t['ink'] if aberta else t['muted']))
            p.drawText(r.adjusted(30, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, f'Catraca {i + 1}' if aberta else 'fechada')
        # setas de entrada e saída
        p.setPen(QColor(t['muted']))
        p.drawText(QRectF(self.cat_x + self.CAT_W + 6, self.topo, 60, self.CAT_H), Qt.AlignVCenter | Qt.AlignLeft, 'saída →')
        # alunos
        cores = {'espera': t['espera'], 'catraca': t['cat'], 'passou': t['ok'], 'desistiu': t['alert']}
        p.setPen(Qt.NoPen)
        for al in self.fila + [a for a in self.cats if a] + self.saindo:
            cor = QColor(cores[al.estado])
            cor.setAlphaF(max(0.0, min(1.0, al.a)))
            p.setBrush(cor)
            p.drawEllipse(QPointF(al.x, al.y), 5.2, 5.2)
        excesso = len(self.fila) - self.cap * self.linhas
        if excesso > 0:
            x, y = self.pos_fila(self.cap * self.linhas - 1)
            p.setPen(QColor(t['ink']))
            p.drawText(QPointF(x - 4, y + 18), f'+{excesso}')
        if self.aviso_k > 0:
            cor = QColor(t['alert'])
            cor.setAlphaF(self.aviso_k)
            p.setPen(cor)
            p.drawText(QRectF(8, self.height() - 22, 300, 18), Qt.AlignLeft, f'fila cheia (K = {self.K}): aluno não entrou')


class LinhaTempo(QWidget):
    """Mini gráfico da réplica animada; clicar ou arrastar muda o momento."""
    buscar = Signal(int)

    def __init__(self, tema):
        super().__init__()
        self.t = tema
        self.hist = None
        self.k = -1
        self.setFixedHeight(58)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)

    def carregar(self, hist, media, pico, passo):
        self.hist, self.media, self.pico, self.passo = hist, media, pico, passo
        self.ymax = max(max(hist), max(media), 1)
        self.update()

    def definir(self, k):
        self.k = k
        self.update()

    def _x(self, i):
        return 6 + (i + 1) / len(self.hist) * (self.width() - 12)

    def _k(self, x):
        return int(round((x - 6) / (self.width() - 12) * len(self.hist))) - 1

    def mousePressEvent(self, ev):
        if self.hist:
            self.buscar.emit(self._k(ev.position().x()))

    def mouseMoveEvent(self, ev):
        if self.hist and ev.buttons():
            self.buscar.emit(self._k(ev.position().x()))

    def keyPressEvent(self, ev):
        if not self.hist:
            return
        passo_min = int(60 / self.passo)
        if ev.key() == Qt.Key_Right:
            self.buscar.emit(self.k + passo_min)
        elif ev.key() == Qt.Key_Left:
            self.buscar.emit(self.k - passo_min)
        else:
            super().keyPressEvent(ev)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = self.t
        if not self.hist:
            return
        h, base = self.height() - 8, self.height() - 4
        T = len(self.pico)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t['pico']))
        for m, pk in enumerate(self.pico):
            if pk:
                x0 = 6 + m / T * (self.width() - 12)
                p.drawRect(QRectF(x0, 2, (self.width() - 12) / T + 0.5, h + 2))
        y = lambda v: base - v / self.ymax * (h - 4)
        passo = max(1, len(self.hist) // max(1, self.width()))
        for serie, cor, larg, tracejado in ((self.media, t['muted'], 1.2, True), (self.hist, t['series']['base'], 1.6, False)):
            cam = QPainterPath()
            for j, i in enumerate(range(0, len(serie), passo)):
                pt = QPointF(self._x(i), y(serie[i]))
                cam.moveTo(pt) if j == 0 else cam.lineTo(pt)
            pen = QPen(QColor(cor), larg)
            if tracejado:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(cam)
        x = self._x(max(self.k, -1))
        p.setPen(QPen(QColor(t['ink']), 2))
        p.drawLine(QPointF(x, 0), QPointF(x, self.height()))
        if self.hasFocus():
            p.setPen(QPen(QColor(t['accent']), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 6, 6)


# =================================================================== gráficos (matplotlib)
def _fonte_mpl():
    nomes = {f.name for f in font_manager.fontManager.ttflist}
    for n in ('Segoe UI', 'Inter', 'Helvetica Neue', 'Arial'):
        if n in nomes:
            return [n, 'DejaVu Sans']
    return ['DejaVu Sans']


class Grafico(FigureCanvasQTAgg):
    def __init__(self, altura=290):
        self.fig = Figure(figsize=(8, altura / 100), dpi=100, layout='constrained')
        super().__init__(self.fig)
        self.setMinimumHeight(altura)
        self.ax = self.fig.add_subplot()
        self.dica = None
        self.cursor = None
        self.mpl_connect('motion_notify_event', self._mover)
        self.mpl_connect('figure_leave_event', lambda _: self._sair())

    def limpar(self, t, t0):
        self.fig.clear()
        self.fig.set_facecolor(t['surface'])
        ax = self.ax = self.fig.add_subplot()
        ax.set_facecolor(t['surface'])
        for s in ('top', 'right'):
            ax.spines[s].set_visible(False)
        for s in ('left', 'bottom'):
            ax.spines[s].set_color(t['line'])
        ax.tick_params(colors=t['muted'], labelsize=8.5, length=0, pad=6)
        ax.grid(axis='y', color=t['line'], lw=.7)
        ax.set_axisbelow(True)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=10, steps=[1, 2, 2.5, 5, 10]))
        if t0 is not None:
            ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: (t0 + timedelta(minutes=x)).strftime('%H:%M')))
        else:
            ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{x:.0f} min'))
        self.cursor = ax.axvline(0, color=t['muted'], lw=.9, alpha=0)
        self.dica = None
        return ax

    def faixas_pico(self, pico, cor):
        m = 0
        while m < len(pico):
            if pico[m]:
                f = m
                while f < len(pico) and pico[f]:
                    f += 1
                self.ax.axvspan(m, f, color=cor, lw=0, zorder=0)
                m = f
            else:
                m += 1

    def _mover(self, ev):
        if ev.inaxes is not self.ax or not self.dica or ev.xdata is None:
            self._sair()
            return
        x, html = self.dica(ev.xdata)
        self.cursor.set_xdata([x, x])
        self.cursor.set_alpha(.7)
        self.draw_idle()
        QToolTip.showText(QCursor.pos() + QPoint(16, 12), html, self)

    def _sair(self):
        if self.cursor is not None and self.cursor.get_alpha():
            self.cursor.set_alpha(0)
            self.draw_idle()
        QToolTip.hideText()


# =================================================================== cartão de cenário
class Cartao(QFrame):
    clicado = Signal(str)

    def __init__(self, nome, r, base, t):
        super().__init__()
        self.setObjectName('cartao')
        self.nome = nome
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip('Clique para ver este cenário na animação')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(2)
        topo = QHBoxLayout()
        risco = QFrame()
        risco.setFixedSize(18, 4)
        risco.setStyleSheet(f'background: {t["series"][r["chave"]]}; border-radius: 2px; border: none;')
        topo.addWidget(risco, 0, Qt.AlignVCenter)
        topo.addWidget(rotulo(NOMES_LONGOS[r['chave']].upper(), 'rotulo', quebra=True), 1)
        lay.addLayout(topo)
        lay.addSpacing(4)
        lay.addWidget(rotulo(f'{br(r["W"], 1)} min', 'grande'))
        lay.addWidget(rotulo(f'tempo médio no sistema (± {br(r["Wic"], 1)})', 'dica'))
        if r is not base and base['W'] > 0:
            dif = (r['W'] - base['W']) / base['W']
            txt = f'{"−" if dif < 0 else "+"}{br(abs(dif) * 100, 0)}% de espera contra 1 catraca'
            lay.addWidget(rotulo(txt, 'bom' if dif < 0 else 'ruim', quebra=True))
        else:
            lay.addWidget(rotulo('situação atual', 'dica'))
        lay.addSpacing(8)
        g = QGridLayout()
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(2)
        for i, (rot, val) in enumerate((('alunos em média', br(r['L'], 1)), ('pior momento', br(r['pior'], 1)),
                                         ('tempo com fila ≥ 10', pct(r['longa'])))):
            g.addWidget(rotulo(rot, 'dica'), i, 0)
            v = rotulo(val)
            v.setStyleSheet('font-weight: 600;')
            g.addWidget(v, i, 1, Qt.AlignRight)
        lay.addLayout(g)

    def selecionar(self, sim):
        self.setProperty('sel', 'true' if sim else 'false')
        repolir(self)

    def mousePressEvent(self, _):
        self.clicado.emit(self.nome)


# =================================================================== janela
class Janela(QMainWindow):
    def __init__(self, arquivos_iniciais):
        super().__init__()
        self.setWindowTitle('Simulador da fila da catraca · RU UFOPA')
        self.resize(1400, 900)
        hints = QGuiApplication.styleHints()
        escuro = hasattr(hints, 'colorScheme') and hints.colorScheme() == Qt.ColorScheme.Dark
        self.nome_tema = 'escuro' if escuro else 'claro'
        self.t = dict(TEMAS[self.nome_tema])
        self.fontes = []
        self.med = None
        self.medido = {}
        self.editado = set()
        self._prog = False
        self.saida = None
        self.rodada = None
        self.anim_nome = '1 catraca'
        self.anim_rep = 0
        self.cartoes = {}
        self._montar()
        self.aplicar_tema()
        self._carregar_exemplos()
        if arquivos_iniciais:
            self.abrir_csvs(arquivos_iniciais)
        elif self.fontes:
            self.fonte.setCurrentIndex(0)
            self.trocar_fonte()

    # ------------------------------------------------------------ montagem
    def _montar(self):
        raiz = QWidget()
        raiz.setObjectName('raiz')
        self.setCentralWidget(raiz)
        geral = QVBoxLayout(raiz)
        geral.setContentsMargins(20, 16, 20, 16)
        geral.setSpacing(14)

        cab = QHBoxLayout()
        tit = QVBoxLayout()
        tit.setSpacing(2)
        tit.addWidget(rotulo('Simulador da fila da catraca', nome='titulo'))
        tit.addWidget(rotulo('RU da UFOPA · Avaliação de Desempenho · cadeia de Markov do analise_catraca.py', 'dica'))
        cab.addLayout(tit, 1)
        self.btn_tema = QPushButton()
        self.btn_tema.clicked.connect(self.trocar_tema)
        cab.addWidget(self.btn_tema, 0, Qt.AlignVCenter)
        geral.addLayout(cab)

        corpo = QHBoxLayout()
        corpo.setSpacing(16)
        geral.addLayout(corpo, 1)

        # ---- barra lateral
        lateral = QScrollArea()
        lateral.setWidgetResizable(True)
        lateral.setFixedWidth(350)
        lateral.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        miolo = QWidget()
        miolo.setObjectName('miolo')
        lat = QVBoxLayout(miolo)
        lat.setContentsMargins(0, 0, 8, 0)
        lat.setSpacing(12)
        lateral.setWidget(miolo)
        corpo.addWidget(lateral)

        # dados
        f, l = card()
        l.addWidget(rotulo('Dados', nome='h2'))
        self.fonte = QComboBox()
        self.fonte.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.fonte.setMinimumContentsLength(12)
        self.fonte.currentIndexChanged.connect(lambda _: self.trocar_fonte())
        l.addWidget(self.fonte)
        self.fonte_desc = rotulo('', 'dica', quebra=True)
        l.addWidget(self.fonte_desc)
        b = QPushButton('Abrir CSVs da coleta…')
        b.clicked.connect(lambda: self.abrir_csvs())
        l.addWidget(b)
        self.msg_arquivos = rotulo('', 'erro', quebra=True)
        self.msg_arquivos.hide()
        l.addWidget(self.msg_arquivos)
        lat.addWidget(f)

        # parâmetros
        f, l = card()
        l.addWidget(rotulo('Chegadas e atendimento', nome='h2'))
        self.caixa_manual = QWidget()
        gm = QGridLayout(self.caixa_manual)
        gm.setContentsMargins(0, 0, 0, 0)
        gm.setHorizontalSpacing(10)
        self.m_T = self._spin(QSpinBox, 5, 600, 105)
        self.m_pi = self._spin(QSpinBox, 0, 600, 20)
        self.m_pf = self._spin(QSpinBox, 0, 600, 60)
        for col, (rot, w) in enumerate((('Duração (min)', self.m_T), ('Pico do min', self.m_pi), ('até o min', self.m_pf))):
            gm.addWidget(rotulo(rot, 'campo'), 0, col)
            gm.addWidget(w, 1, col)
        l.addWidget(self.caixa_manual)

        self.campos = {}
        g = QGridLayout()
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(2)
        defs = [
            ('lam_cal', 'λ calma', 'chegadas/min', QDoubleSpinBox, 0, 60, 2),
            ('lam_pic', 'λ pico', 'chegadas/min', QDoubleSpinBox, 0, 60, 2),
            ('mu', 'μ por catraca', 'atendimentos/min', QDoubleSpinBox, 0.1, 60, 2),
            ('theta', 'θ desistência', '/min por aluno', QDoubleSpinBox, 0, 5, 3),
            ('n0', 'Fila inicial', 'alunos no sistema', QSpinBox, 0, 999, 0),
            ('limiar', 'Limiar de pico', 'chegadas/min', QDoubleSpinBox, 0, 60, 2),
        ]
        for i, (k, nome, unid, cls, lo, hi, dec) in enumerate(defs):
            r, c = divmod(i, 2)
            caixa = QVBoxLayout()
            caixa.setSpacing(3)
            caixa.addWidget(rotulo(f'{nome}<br><span style="font-weight:400">{unid}</span>', 'campo'))
            w = self._spin(cls, lo, hi, 0, dec)
            if k == 'limiar':
                w.setSpecialValueText('automático')
                w.valueChanged.connect(self._limiar_mudou)
            else:
                w.valueChanged.connect(lambda _v, k=k: self._editou(k))
            caixa.addWidget(w)
            med = rotulo('', 'medido', quebra=True)
            caixa.addWidget(med)
            self.campos[k] = (w, med)
            g.addLayout(caixa, r, c)
        l.addLayout(g)
        for w in (self.m_T, self.m_pi, self.m_pf):
            w.valueChanged.connect(lambda _v: self._pendente())
        self.btn_medidos = QPushButton('↺ Voltar aos valores medidos')
        self.btn_medidos.setProperty('papel', 'fino')
        self.btn_medidos.clicked.connect(self.restaurar_medidos)
        l.addWidget(self.btn_medidos)
        lat.addWidget(f)

        # cenários
        f, l = card()
        l.addWidget(rotulo('Cenários', nome='h2'))
        self.checks = {}
        for k in ('base', 'semdes', 'pico2', 'toda2', 'pers'):
            cb = QCheckBox(NOMES_LONGOS[k])
            cb.setChecked(k != 'pers')
            if k == 'base':
                cb.setEnabled(False)
                cb.setToolTip('Sempre simulado: é a base da validação.')
            cb.toggled.connect(lambda _v: self._pendente())
            self.checks[k] = cb
            l.addWidget(cb)
        self.caixa_pers = QWidget()
        gp = QGridLayout(self.caixa_pers)
        gp.setContentsMargins(24, 2, 0, 0)
        gp.setHorizontalSpacing(10)
        self.pers_calma = self._spin(QSpinBox, 1, 6, 1)
        self.pers_pico = self._spin(QSpinBox, 1, 6, 3)
        self.pers_desist = QCheckBox('com desistência')
        self.pers_desist.setChecked(True)
        gp.addWidget(rotulo('Catracas na calma', 'campo'), 0, 0)
        gp.addWidget(rotulo('Catracas no pico', 'campo'), 0, 1)
        gp.addWidget(self.pers_calma, 1, 0)
        gp.addWidget(self.pers_pico, 1, 1)
        gp.addWidget(self.pers_desist, 2, 0, 1, 2)
        for w in (self.pers_calma, self.pers_pico):
            w.valueChanged.connect(lambda _v: self._pendente())
        self.pers_desist.toggled.connect(lambda _v: self._pendente())
        self.checks['pers'].toggled.connect(self.caixa_pers.setVisible)
        self.caixa_pers.setVisible(False)
        l.addWidget(self.caixa_pers)
        lat.addWidget(f)

        # simulação
        f, l = card()
        l.addWidget(rotulo('Simulação', nome='h2'))
        g = QGridLayout()
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(3)
        self.p_K = self._spin(QSpinBox, 5, 2000, 80)
        self.p_reps = self._spin(QSpinBox, 2, 5000, 500)
        self.p_seed = self._spin(QSpinBox, 0, 2_000_000_000, 42)
        self.p_passo = self._spin(QDoubleSpinBox, 0.5, 60, 5, 1)
        for i, (rot, w) in enumerate((('Capacidade K', self.p_K), ('Réplicas', self.p_reps),
                                      ('Semente', self.p_seed), ('Passo (s)', self.p_passo))):
            r, c = divmod(i, 2)
            g.addWidget(rotulo(rot, 'campo'), r * 2, c)
            g.addWidget(w, r * 2 + 1, c)
            w.valueChanged.connect(lambda _v: self._pendente())
        l.addLayout(g)
        l.addSpacing(4)
        self.btn_sim = QPushButton('Simular')
        self.btn_sim.setProperty('papel', 'primario')
        self.btn_sim.clicked.connect(self.simular)
        l.addWidget(self.btn_sim)
        self.barra = QProgressBar()
        self.barra.setTextVisible(False)
        self.barra.hide()
        l.addWidget(self.barra)
        self.msg_sim = rotulo('', 'dica', quebra=True)
        l.addWidget(self.msg_sim)
        lat.addWidget(f)
        lat.addStretch(1)

        # ---- resultados em abas
        self.abas = QTabWidget()
        self.abas.setDocumentMode(True)
        corpo.addWidget(self.abas, 1)
        self.abas.addTab(self._aba_geral(), 'Visão geral')
        self.abas.addTab(self._aba_graficos(), 'Gráficos')
        self.abas.addTab(self._aba_tabelas(), 'Modelo e validação')

    def _rolagem(self):
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        w = QWidget()
        w.setObjectName('miolo')
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 12, 8, 12)
        lay.setSpacing(14)
        sa.setWidget(w)
        return sa, lay

    def _aba_geral(self):
        sa, lay = self._rolagem()
        f, l = card()
        l.addWidget(rotulo('CONCLUSÃO', 'rotulo'))
        self.conclusao = rotulo('Simulando…', 'conclusao', quebra=True)
        l.addWidget(self.conclusao)
        self.selo_valid = rotulo('', 'dica', quebra=True)
        l.addWidget(self.selo_valid)
        lay.addWidget(f)

        self.grade_cartoes = QGridLayout()
        self.grade_cartoes.setSpacing(12)
        lay.addLayout(self.grade_cartoes)

        f, l = card()
        topo = QHBoxLayout()
        tx = QVBoxLayout()
        tx.setSpacing(2)
        tx.addWidget(rotulo('A fila andando', nome='h2'))
        tx.addWidget(rotulo('Uma réplica da simulação, passo a passo. Clique num cartão acima para trocar o cenário.', 'dica', quebra=True))
        topo.addLayout(tx, 1)
        self.anim_nome_lb = rotulo('', 'rotulo')
        topo.addWidget(self.anim_nome_lb, 0, Qt.AlignTop)
        l.addLayout(topo)

        placar = QHBoxLayout()
        placar.setSpacing(22)
        caixa = QVBoxLayout()
        caixa.setSpacing(0)
        caixa.addWidget(rotulo('HORÁRIO', 'rotulo'))
        self.a_hora = rotulo('--:--', 'num')
        caixa.addWidget(self.a_hora)
        placar.addLayout(caixa)
        self.a_fase = rotulo('calma', 'selo-calma')
        placar.addWidget(self.a_fase, 0, Qt.AlignVCenter)
        self.a_nums = {}
        for k, rot in (('esp', 'esperando'), ('cat', 'na catraca'), ('cheg', 'chegaram'),
                       ('pass', 'passaram'), ('des', 'desistiram'), ('abertas', 'catracas abertas')):
            cx = QVBoxLayout()
            cx.setSpacing(0)
            n = rotulo('0', 'num')
            cx.addWidget(n)
            cx.addWidget(rotulo(rot, 'dica'))
            self.a_nums[k] = n
            placar.addLayout(cx)
        placar.addStretch(1)
        l.addLayout(placar)

        self.palco = Palco(self.t)
        self.palco.mudou.connect(self._anim_mudou)
        self.palco.terminou.connect(lambda: self.btn_play.setText('▶  Reproduzir'))
        l.addWidget(self.palco)
        self.linha = LinhaTempo(self.t)
        self.linha.buscar.connect(self.palco.ir_para)
        l.addWidget(self.linha)
        leg = rotulo('', 'dica', quebra=True)
        self.leg_anim = leg
        l.addWidget(leg)

        ctl = QHBoxLayout()
        ctl.setSpacing(8)
        self.btn_play = QPushButton('▶  Reproduzir')
        self.btn_play.setProperty('papel', 'primario')
        self.btn_play.clicked.connect(self._play)
        ctl.addWidget(self.btn_play)
        ctl.addSpacing(8)
        ctl.addWidget(rotulo('Velocidade', 'campo'))
        self.grupo_vel = QButtonGroup(self)
        for v in (5, 15, 30, 60, 120):
            b = QPushButton(f'{v}×')
            b.setProperty('papel', 'seg')
            b.setCheckable(True)
            b.setChecked(v == 30)
            self.grupo_vel.addButton(b, v)
            ctl.addWidget(b)
        self.grupo_vel.idClicked.connect(lambda v: setattr(self.palco, 'vel', v))
        ctl.addSpacing(8)
        b = QPushButton('↻  Outra réplica')
        b.clicked.connect(self._outra_replica)
        ctl.addWidget(b)
        ctl.addStretch(1)
        l.addLayout(ctl)
        lay.addWidget(f)
        lay.addStretch(1)
        return sa

    def _aba_graficos(self):
        sa, lay = self._rolagem()
        self.g_cheg = Grafico(270)
        self.g_valid = Grafico(320)
        self.g_cen = Grafico(320)
        self.card_valid = None
        for tit, dica, g in (
            ('Chegadas por minuto', 'Faixa rosada = minutos de pico. As linhas tracejadas são a capacidade com 1 e 2 catracas: '
             'quando as chegadas passam da capacidade, a fila cresce. Passe o mouse para ver os valores.', self.g_cheg),
            ('Validação: fila reconstruída × simulada', 'Pontos = alunos no sistema reconstruídos a partir dos eventos da coleta. '
             'Linha = média das réplicas com 1 catraca; faixa = 5% a 95% das réplicas.', self.g_valid),
            ('Cenários ao longo do tempo', 'Alunos no sistema, média das réplicas. Mesma semente em todos os cenários.', self.g_cen),
        ):
            f, l = card()
            l.addWidget(rotulo(tit, nome='h2'))
            l.addWidget(rotulo(dica, 'dica', quebra=True))
            l.addWidget(g)
            lay.addWidget(f)
            if g is self.g_valid:
                self.card_valid = f
        lay.addStretch(1)
        return sa

    def _aba_tabelas(self):
        sa, lay = self._rolagem()
        self.tabs = {}
        for k, tit, dica in (
            ('cen', 'Cenários', '± é o IC de 95% entre réplicas. Uma hora simulada é uma amostra, não uma medida.'),
            ('valid', 'Validação (slide 22)', 'Fila reconstruída × simulada nos mesmos instantes. Se algum item ficar fora da faixa, '
             'revejam primeiro as medições: contagens, separação calma/pico e os atendimentos cronometrados.'),
            ('mm1', 'Modelo M/M/1 por trecho', ''),
            ('verif', 'Verificação (slide 19)', 'Simulador com λ de calma e 1 catraca por 200 h simuladas contra as fórmulas. '
             'Se os dois lados ficam próximos, o código faz o que o modelo diz.'),
        ):
            f, l = card()
            l.addWidget(rotulo(tit, nome='h2'))
            tb = QTableWidget()
            tb.setEditTriggers(QTableWidget.NoEditTriggers)
            tb.setSelectionMode(QTableWidget.NoSelection)
            tb.setFocusPolicy(Qt.NoFocus)
            tb.verticalHeader().hide()
            tb.setAlternatingRowColors(True)
            tb.setShowGrid(False)
            tb.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            tb.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            l.addWidget(tb)
            info = rotulo(dica, 'dica', quebra=True)
            l.addWidget(info)
            self.tabs[k] = (tb, info, f)
            lay.addWidget(f)
        lay.addStretch(1)
        return sa

    def _spin(self, cls, lo, hi, val, dec=2):
        w = cls()
        w.setRange(lo, hi)
        if cls is QDoubleSpinBox:
            w.setDecimals(dec)
            w.setSingleStep(10 ** -min(dec, 2) if dec else 1)
        w.setValue(val)
        w.setKeyboardTracking(False)
        return w

    # ------------------------------------------------------------ tema
    def trocar_tema(self):
        self.nome_tema = 'claro' if self.nome_tema == 'escuro' else 'escuro'
        self.aplicar_tema()

    def aplicar_tema(self):
        self.t.clear()
        self.t.update(TEMAS[self.nome_tema])  # o mesmo dicionário é usado pelo palco e pela linha do tempo
        QApplication.instance().setStyleSheet(qss(self.t))
        self.btn_tema.setText('☀  Tema claro' if self.nome_tema == 'escuro' else '☾  Tema escuro')
        if self.saida:
            self.mostrar(self.saida, manter_anim=True)
        self.palco.update()
        self.linha.update()

    # ------------------------------------------------------------ fontes de dados
    def _carregar_exemplos(self):
        for rot, rel, mu, K, desc in EXEMPLOS:
            caminho = os.path.join(PASTA, rel)
            if not os.path.exists(caminho):
                continue
            sess = ac.ler([caminho])
            for nome, s in sorted(sess.items()):
                d = ac.preparar(nome, s)
                if d:
                    self.fontes.append({'rotulo': rot, 'desc': desc, 'd': d, 'mu': mu, 'K': K,
                                        't0': min(s['inicio']) if s['inicio'] else None, 'mu_txt': 'do LEIA-ME'})
        self.fontes.append({'rotulo': 'Modelo manual (sem dados)', 'd': None, 'mu': 4.94, 'K': 80, 't0': None,
                            'desc': 'Escolha a duração, o trecho de pico e as taxas. Sem dados não há validação.'})
        self._encher_combo()

    def _encher_combo(self, atual=None):
        self._prog = True
        self.fonte.clear()
        for f in self.fontes:
            self.fonte.addItem(f['rotulo'])
        self._prog = False
        if atual is not None:
            self.fonte.setCurrentIndex(atual)

    def abrir_csvs(self, caminhos=None):
        if caminhos is None:
            caminhos, _ = QFileDialog.getOpenFileNames(self, 'CSVs da coleta (observadores A, B e C)', PASTA, 'CSV (*.csv);;Todos (*)')
            if not caminhos:
                return
        self.msg_arquivos.hide()
        try:
            sess = ac.ler(caminhos)
        except Exception as e:  # noqa: BLE001
            self.msg_arquivos.setText(f'Não consegui ler os arquivos: {e}')
            self.msg_arquivos.show()
            return
        dados = [(ac.preparar(n, s), s) for n, s in sorted(sess.items())]
        dados = [(d, s) for d, s in dados if d]
        if not dados:
            self.msg_arquivos.setText('Nenhuma sessão encontrada. Os arquivos precisam ser os CSVs exportados pela página de coleta.')
            self.msg_arquivos.show()
            return
        atend = [a for d, _ in dados for a in d['atend'] if a > 0]
        if atend:
            m = sum(atend) / len(atend)
            mu, mu_txt = 60 / m, f'{len(atend)} atendimentos cronometrados'
            if len(atend) > 1:
                cv = statistics.stdev(atend) / m
                mu_txt += f', CV = {br(cv)}'
        else:
            mu, mu_txt = None, None
        primeiro = len(self.fontes) - 1  # antes do "Modelo manual"
        for d, s in dados:
            desc = f'{len(caminhos)} arquivo(s) · {d["T"]} min · {sum(d["arr"])} chegadas · {sum(d["des"])} desistências.'
            if mu is None:
                desc += ' Sem atendimentos cronometrados: confira o μ.'
            todos = s['inicio'] + s['chegada'] + s['saida_atend']
            self.fontes.insert(len(self.fontes) - 1, {
                'rotulo': f'{d["nome"]} (arquivo)', 'desc': desc, 'd': d, 'mu': mu, 'K': None,
                't0': min(s['inicio']) if s['inicio'] else (min(todos) if todos else None), 'mu_txt': mu_txt})
        self._encher_combo(primeiro)
        self.trocar_fonte()

    def fonte_atual(self):
        i = self.fonte.currentIndex()
        return self.fontes[i] if 0 <= i < len(self.fontes) else None

    def trocar_fonte(self):
        if self._prog:
            return
        f = self.fonte_atual()
        if not f:
            return
        self.fonte_desc.setText(f['desc'])
        manual = f['d'] is None
        self.caixa_manual.setVisible(manual)
        self.campos['limiar'][0].setEnabled(not manual)
        self.btn_medidos.setVisible(not manual)
        if self.card_valid is not None:
            self.card_valid.setVisible(not manual)
        self._prog = True
        if f['K']:
            self.p_K.setValue(f['K'])
        self.campos['limiar'][0].setValue(0)
        self._prog = False
        if not manual and sum(f['d']['arr']) == 0:
            self.msg_arquivos.setText('Esta sessão não tem chegadas registradas (o CSV do observador A está junto?).')
            self.msg_arquivos.show()
        self.restaurar_medidos()
        self.simular()

    # ------------------------------------------------------------ campos
    def _limiar_mudou(self):
        if self._prog:
            return
        self.restaurar_medidos(manter_mu=True)

    def restaurar_medidos(self, manter_mu=False):
        """Preenche os campos com o que foi medido na sessão. manter_mu=True (troca de limiar) preserva um μ digitado."""
        f = self.fonte_atual()
        mu_digitado = manter_mu and 'mu' in self.editado
        self.editado.clear()
        self.medido = {}
        self._prog = True
        if f['d'] is None:
            self.med = None
            for k, v in (('lam_cal', 3.5), ('lam_pic', 8.0), ('theta', 0.05), ('n0', 0), ('mu', f['mu'])):
                self.campos[k][0].setValue(v)
            for k in self.campos:
                self.campos[k][1].setText('')
        else:
            lim = self.campos['limiar'][0].value() or None
            self.med = md = ac.medir(f['d'], lim)
            self.medido = {'lam_cal': md['lam_cal'], 'lam_pic': md['lam_pic'], 'theta': md['theta'], 'n0': md['n0']}
            if mu_digitado:
                self.editado.add('mu')
            elif f['mu'] is not None:
                self.medido['mu'] = f['mu']
            for k, v in self.medido.items():
                self.campos[k][0].setValue(v if v is not None else 0)
            self.campos['lam_cal'][1].setText(f'medido: {br(md["lam_cal"])} em {len(md["cal_m"])} min')
            self.campos['lam_pic'][1].setText(f'medido: {br(md["lam_pic"])} em {len(md["pic_m"])} min' if md['lam_pic'] is not None else 'sem pico detectado')
            self.campos['theta'][1].setText(f'medido: {br(md["theta"], 3)} ({md["D"]} desistências)')
            self.campos['n0'][1].setText(f'medido: {md["n0"]}')
            self.campos['mu'][1].setText(f'{f.get("mu_txt") or "informado"}: {br(f["mu"])}' if f['mu'] is not None else 'sem cronometragem: informe μ')
            limtxt = br(md['limiar']) if md['limiar'] != float('inf') else 'sem pico claro'
            self.campos['limiar'][1].setText(('automático: ' if not lim else 'usado: ') + limtxt)
        self._prog = False
        for k in self.campos:
            self._marcar(k)
        self._pendente()

    def _editou(self, k):
        if self._prog:
            return
        self.editado.add(k)
        self._marcar(k)
        self._pendente()

    def _marcar(self, k):
        w = self.campos[k][0]
        w.setProperty('editado', 'true' if (k in self.editado and k in self.medido) else 'false')
        repolir(w)

    def _pendente(self):
        if self._prog or self.saida is None:
            return
        self.msg_sim.setText('Parâmetros alterados: clique em Simular para atualizar os resultados.')
        self.btn_sim.setText('Simular de novo')

    def valor(self, k):
        if k in self.medido and k not in self.editado:
            return self.medido[k]
        return self.campos[k][0].value()

    def configuracao(self):
        f = self.fonte_atual()
        sel = {k for k, cb in self.checks.items() if cb.isChecked()}
        c = {'d': f['d'], 't0': f['t0'], 'mu': self.valor('mu'), 'theta': self.valor('theta'), 'n0': int(self.valor('n0')),
             'K': self.p_K.value(), 'reps': self.p_reps.value(), 'seed': self.p_seed.value(), 'passo': self.p_passo.value(),
             'sel': sel, 'pers': (self.pers_calma.value(), self.pers_pico.value(), self.pers_desist.isChecked())}
        if f['d'] is None:
            T = self.m_T.value()
            pi, pf = self.m_pi.value(), self.m_pf.value()
            c['pico'] = [pi <= m < pf for m in range(T)]
            c['lam_cal'] = self.valor('lam_cal') if not all(c['pico']) else None
            c['lam_pic'] = self.valor('lam_pic') if any(c['pico']) else None
        else:
            c['pico'] = self.med['pico']
            c['lam_cal'] = self.valor('lam_cal') if self.med['lam_cal'] is not None else None
            c['lam_pic'] = self.valor('lam_pic') if self.med['lam_pic'] is not None else None
        c['T'] = len(c['pico'])
        lams = ac.lams_por_minuto(c['pico'], c['lam_cal'], c['lam_pic'], 0)
        if f['d'] is not None and not ({'lam_cal', 'lam_pic'} & self.editado):
            c['lam_med'] = self.med['lam_med']  # o mesmo λ médio do relatório (W = L / λ)
        else:
            c['lam_med'] = sum(lams) / len(lams)
        return c

    # ------------------------------------------------------------ simulação
    def simular(self):
        if self.rodada and self.rodada.isRunning():
            return
        f = self.fonte_atual()
        if f is None:
            return
        if f['d'] is not None and sum(f['d']['arr']) == 0:
            return
        if f['d'] is None and self.m_pf.value() <= self.m_pi.value():
            self.msg_sim.setText('O fim do pico precisa vir depois do começo.')
            return
        cfg = self.configuracao()
        if cfg['lam_med'] <= 0:
            self.msg_sim.setText('Informe λ maior que zero.')
            return
        self.btn_sim.setEnabled(False)
        self.btn_sim.setText('Simulando…')
        self.barra.setValue(0)
        self.barra.show()
        self.msg_sim.setText(f'{cfg["reps"]} réplicas por cenário…')
        self.palco.tocar(False)
        self.rodada = Rodada(cfg)
        self.rodada.progresso.connect(self.barra.setValue)
        self.rodada.pronto.connect(self._pronto)
        self.rodada.falhou.connect(self._falhou)
        self.rodada.start()

    def _fim_rodada(self):
        self.btn_sim.setEnabled(True)
        self.btn_sim.setText('Simular')
        self.barra.hide()

    def _falhou(self, msg):
        self._fim_rodada()
        self.msg_sim.setText('')
        QMessageBox.warning(self, 'Simulação', msg)

    def _pronto(self, saida):
        self._fim_rodada()
        self.saida = saida
        c = saida['cfg']
        txt = f'{c["reps"]} réplicas · passo {br(saida["passo"], 1)} s · K = {c["K"]} · semente {c["seed"]}.'
        self.msg_sim.setText(' '.join(saida['avisos'] + [txt]))
        if self.anim_nome not in saida['res']:
            self.anim_nome = '1 catraca'
        self.anim_rep = 0
        self.mostrar(saida)

    # ------------------------------------------------------------ resultados
    def mostrar(self, s, manter_anim=False):
        c, res, t = s['cfg'], s['res'], self.t
        base = res['1 catraca']

        # conclusão
        if '2ª só no pico' in res:
            c2 = res['2ª só no pico']
            txt = (f'Uma 2ª catraca só no pico muda o tempo médio no sistema de {br(base["W"], 1)} para '
                   f'{br(c2["W"], 1)} min, e os alunos em média de {br(base["L"], 1)} para {br(c2["L"], 1)}.')
            if c['lam_pic'] is not None:
                txt += f' No pico chegam {br(c["lam_pic"])} alunos/min, contra μ = {br(c["mu"])} de uma catraca.'
        elif '2 a hora toda' in res:
            c2 = res['2 a hora toda']
            txt = (f'Sem pico detectado. Com 2 catracas a hora toda, o tempo médio no sistema vai de {br(base["W"], 1)} '
                   f'para {br(c2["W"], 1)} min.')
        else:
            txt = f'Com 1 catraca, o tempo médio no sistema é {br(base["W"], 1)} min e há {br(base["L"], 1)} alunos em média.'
        self.conclusao.setText(txt)
        if s.get('valid'):
            ok = sum(v['ok'] for v in s['valid'])
            self.selo_valid.setText(f'{"✓" if ok == 3 else "⚠"}  Validação: {ok} de 3 itens da fila reconstruída dentro da faixa '
                                    '5%–95% das réplicas (aba Modelo e validação).')
            self.selo_valid.setProperty('papel', 'bom' if ok == 3 else 'ruim')
        else:
            self.selo_valid.setText('Sem fila reconstruída: não há validação para este caso.')
            self.selo_valid.setProperty('papel', 'dica')
        repolir(self.selo_valid)

        # cartões
        while self.grade_cartoes.count():
            w = self.grade_cartoes.takeAt(0).widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        self.cartoes = {}
        cols = 3 if len(res) == 5 else max(1, len(res))
        for col in range(5):
            self.grade_cartoes.setColumnStretch(col, 1 if col < cols else 0)
        for i, (nome, r) in enumerate(res.items()):
            ct = Cartao(nome, r, base, t)
            ct.clicado.connect(self._escolher_anim)
            self.cartoes[nome] = ct
            self.grade_cartoes.addWidget(ct, i // cols, i % cols)
        self._graficos(s)
        self._tabelas(s)
        if manter_anim:
            self._destacar()
        else:
            self._preparar_anim()

    def _graficos(self, s):
        c, res, t = s['cfg'], s['res'], self.t
        t0, passo, pico, T = c['t0'], s['passo'], c['pico'], c['T']
        hora = (lambda m: (t0 + timedelta(minutes=m)).strftime('%H:%M')) if t0 else (lambda m: f'min {m:.0f}')

        def linha_html(cor, valor, nome):
            return f'<span style="color:{cor}">━━</span>&nbsp;<b>{valor}</b>&nbsp;<span style="color:{t["muted"]}">{nome}</span>'

        def cab(m):
            fase = 'pico' if pico[min(int(m), T - 1)] else 'calma'
            return f'<b>{hora(m)}</b> <span style="color:{t["muted"]}">· minuto {int(m)} · {fase}</span>'

        # chegadas
        g = self.g_cheg
        ax = g.limpar(t, t0)
        g.faixas_pico(pico, t['pico'])
        d = c['d']
        if d:
            ax.bar([m + .5 for m in range(T)], d['arr'], width=.78, color=t['barras'], label='chegadas no minuto', zorder=2)
        ax.step(range(T + 1), s['lams'] + [s['lams'][-1]], where='post', color=t['ink'], lw=1.6, label='λ usado na simulação', zorder=3)
        for mult, estilo, nome in ((1, (0, (5, 3)), '1 catraca'), (2, (0, (1.5, 2.5)), '2 catracas')):
            ax.axhline(c['mu'] * mult, color=t['muted'], lw=1.2, ls=estilo, zorder=3)
            ax.text(T, c['mu'] * mult, f'  capacidade, {nome} ({br(c["mu"] * mult)}/min)', color=t['muted'], fontsize=8,
                    va='bottom', ha='right', bbox=dict(boxstyle='round,pad=0.15', fc=t['surface'], ec='none', alpha=.85))
        ax.set_xlim(0, T)
        ax.set_ylim(0, max(max(d['arr']) if d else 0, max(s['lams']), c['mu'] * 2) * 1.15)
        ax.set_ylabel('alunos por minuto', color=t['muted'], fontsize=9)
        lg = ax.legend(loc='upper left', fontsize=8.5, frameon=False, labelcolor=t['ink'])

        def dica_cheg(x):
            m = max(0, min(int(x), T - 1))
            rows = [cab(m)]
            if d:
                rows.append(linha_html(t['barras'], d['arr'][m], 'chegadas no minuto'))
                if d['des'][m]:
                    rows.append(linha_html(t['alert'], d['des'][m], 'desistências'))
            rows.append(linha_html(t['ink'], br(s['lams'][m]), 'λ usado'))
            return m + .5, '<br>'.join(rows)
        g.dica = dica_cheg
        g.draw_idle()

        # índices de passo -> minutos
        N = len(res["1 catraca"]["hs"][0])
        xs = [(i + 1) * passo / 60 for i in range(N)]

        def idx(x):
            return max(0, min(N - 1, int(round(x * 60 / passo)) - 1))

        # validação
        g = self.g_valid
        ax = g.limpar(t, t0)
        g.faixas_pico(pico, t['pico'])
        b = res['1 catraca']
        cor = t['series']['base']
        ax.fill_between(xs, b['p05'], b['p95'], color=cor, alpha=.16, lw=0, label='5%–95% das réplicas', step='pre')
        ax.step(xs, b['hs'][0], color=cor, lw=.8, alpha=.55, label='1 réplica simulada', where='pre')
        ax.plot(xs, b['media'], color=cor, lw=2.2, label='média das réplicas (1 catraca)')
        fila = d['fila'] if d else []
        if fila:
            ax.scatter([sec / 60 for sec, _ in fila], [n for _, n in fila], s=26, color=t['ink'], zorder=5,
                       edgecolors=t['surface'], linewidths=1.2, label='fila reconstruída')
        ax.set_xlim(0, T)
        ax.set_ylim(bottom=0)
        ax.set_ylabel('alunos no sistema', color=t['muted'], fontsize=9)
        ax.legend(loc='upper right', fontsize=8.5, frameon=False, labelcolor=t['ink'], ncols=2)
        obs = {int(round(sec / 60)): n for sec, n in fila}

        def dica_valid(x):
            m = max(0, min(int(round(x)), T))
            i = idx(m)
            rows = [cab(min(m, T - 1))]
            if m in obs:
                rows.append(linha_html(t['ink'], obs[m], 'fila reconstruída'))
            rows.append(linha_html(cor, br(b['media'][i], 1), 'média das réplicas'))
            rows.append(linha_html(cor, f'{b["p05"][i]:g}–{b["p95"][i]:g}', 'faixa 5%–95%'))
            return m, '<br>'.join(rows)
        g.dica = dica_valid
        g.draw_idle()

        # cenários
        g = self.g_cen
        ax = g.limpar(t, t0)
        g.faixas_pico(pico, t['pico'])
        for nome, r in res.items():
            ax.plot(xs, r['media'], color=t['series'][r['chave']], lw=2, label=f'{NOMES_LONGOS[r["chave"]]} (W = {br(r["W"], 1)} min)',
                    ls=(0, (4, 2)) if r['chave'] == 'semdes' else '-')
        ax.set_xlim(0, T)
        ax.set_ylim(bottom=0)
        ax.set_ylabel('alunos no sistema (média)', color=t['muted'], fontsize=9)
        ax.legend(loc='upper right', fontsize=8.5, frameon=False, labelcolor=t['ink'])

        def dica_cen(x):
            m = max(0, min(int(round(x)), T))
            i = idx(m)
            rows = [cab(min(m, T - 1))]
            for nome, r in sorted(res.items(), key=lambda kv: -kv[1]['media'][i]):
                rows.append(linha_html(t['series'][r['chave']], br(r['media'][i], 1), NOMES_LONGOS[r['chave']]))
            return m, '<br>'.join(rows)
        g.dica = dica_cen
        g.draw_idle()

    def _tabela(self, k, cab, linhas, cores=None):
        tb, _info, _f = self.tabs[k]
        tb.clear()
        tb.setColumnCount(len(cab))
        tb.setRowCount(len(linhas))
        tb.setHorizontalHeaderLabels(cab)
        tb.clearSpans()
        for i, lin in enumerate(linhas):
            for j, val in enumerate(lin):
                if val is None:
                    continue
                it = QTableWidgetItem(str(val))
                it.setTextAlignment((Qt.AlignLeft if j == 0 else Qt.AlignRight) | Qt.AlignVCenter)
                if cores and (i, j) in cores:
                    it.setForeground(QColor(cores[(i, j)]))
                tb.setItem(i, j, it)
            if len(lin) < len(cab):
                tb.setSpan(i, len(lin) - 1, 1, len(cab) - len(lin) + 1)
                tb.item(i, len(lin) - 1).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        tb.resizeRowsToContents()
        h = tb.horizontalHeader().height() + sum(tb.rowHeight(i) for i in range(tb.rowCount())) + 4
        tb.setFixedHeight(h)

    def _tabelas(self, s):
        c, res, t = s['cfg'], s['res'], self.t
        self._tabela('cen', ['cenário', 'L médio', 'pior momento', 'W (min)', 'tempo com fila ≥ 10'],
                     [[NOMES_LONGOS[r['chave']], f'{br(r["L"], 1)} ± {br(r["Lic"], 1)}', br(r['pior'], 1),
                       f'{br(r["W"], 1)} ± {br(r["Wic"], 1)}', pct(r['longa'])] for r in res.values()])

        tb_v, info_v, card_v = self.tabs['valid']
        if s.get('valid'):
            card_v.show()
            linhas, cores = [], {}
            for i, v in enumerate(s['valid']):
                fm = pct if v['casas'] == 2 else (lambda x, d=v['casas']: br(x, d))
                linhas.append([v['rot'], fm(v['obs']), fm(v['sim']), f'{fm(v["lo"])} – {fm(v["hi"])}', '✓ sim' if v['ok'] else '✗ NÃO'])
                cores[(i, 4)] = t['ok'] if v['ok'] else t['alert']
            self._tabela('valid', ['', 'observada', 'simulada (média)', 'faixa 5%–95%', 'dentro?'], linhas, cores)
        else:
            card_v.hide()

        mu, linhas = c['mu'], []
        trechos = [('calma', c['lam_cal']), ('pico', c['lam_pic']), ('sessão', c['lam_med'])]
        for rot, lam in trechos:
            if lam is None:
                continue
            f = ac.formulas(lam, mu)
            if f['estavel']:
                linhas.append([rot, br(lam), br(f['rho']), pct(f['vazia']), br(f['L']), br(f['W']), br(f['Wq'])])
            else:
                linhas.append([rot, br(lam), br(f['rho']), 'ρ ≥ 1: as fórmulas não valem, a fila cresce. Use a simulação.'])
        self._tabela('mm1', ['trecho', 'λ (/min)', 'ρ', 'vazia', 'L', 'W (min)', 'Wq (min)'], linhas)
        md = self.med if c['d'] else None
        partes = [f'μ = {br(mu)} /min (atendimento médio {br(60 / mu, 1)} s) · θ = {br(c["theta"], 3)} /min por aluno que espera.']
        if md:
            partes.append(f'{md["total"]} chegadas em {md["T"]} min (λ médio {br(md["lam_med"])} /min). '
                          f'Calma: {len(md["cal_m"])} min · pico: {len(md["pic_m"])} min.')
            cal = md['cal_m']
            if len(cal) > 2:
                mc = sum(cal) / len(cal)
                vm = statistics.pvariance(cal) / mc if mc else float('nan')
                partes.append(f'Teste rápido de Poisson na calma: variância/média = {br(vm)} (perto de 1 é Poisson).')
            if md['D']:
                partes.append(f'Desistências: {md["D"]} ({br(md["D"] / md["total"] * 100, 0)}% das chegadas).')
        self.tabs['mm1'][1].setText(' '.join(partes))

        if s.get('verif'):
            f, mt = s['verif']
            self.tabs['verif'][2].show()
            self._tabela('verif', ['métrica', 'fórmula', 'simulado'],
                         [['utilização ρ', pct(f['rho']), pct(mt['ocupada'])],
                          ['alunos no sistema L', br(f['L']), br(mt['L'])],
                          ['tempo W (min)', br(f['W']), br(mt['W'])]])
        else:
            self.tabs['verif'][2].hide()

    # ------------------------------------------------------------ animação
    def _escolher_anim(self, nome):
        self.anim_nome = nome
        self.anim_rep = 0
        self._preparar_anim()

    def _outra_replica(self):
        if not self.saida:
            return
        self.anim_rep = (self.anim_rep + 1) % self.saida['cfg']['reps']
        self._preparar_anim()

    def _destacar(self):
        for nome, ct in self.cartoes.items():
            ct.selecionar(nome == self.anim_nome)

    def _preparar_anim(self):
        s = self.saida
        if not s:
            return
        if self.anim_nome not in s['res']:
            self.anim_nome, self.anim_rep = '1 catraca', 0
        c, r = s['cfg'], s['res'][self.anim_nome]
        tocando = self.palco.rodando
        hist = r['hs'][self.anim_rep]
        ev = rastrear(hist, s['lams'], c['mu'], r['cs'], c['n0'], c['K'], c['seed'] + self.anim_rep, s['passo'], r['theta'])
        self.palco.carregar(hist, ev, r['cs'], c['n0'], s['passo'], c['K'])
        self.linha.carregar(list(hist), r['media'], c['pico'], s['passo'])
        self.anim_nome_lb.setText(f'{NOMES_LONGOS[r["chave"]].upper()} · RÉPLICA {self.anim_rep + 1} DE {c["reps"]} · SEMENTE {c["seed"] + self.anim_rep}')
        self.leg_anim.setText(
            f'<span style="color:{self.t["espera"]}">●</span> esperando &nbsp;&nbsp; '
            f'<span style="color:{self.t["cat"]}">●</span> na catraca &nbsp;&nbsp; '
            f'<span style="color:{self.t["ok"]}">●</span> passou &nbsp;&nbsp; '
            f'<span style="color:{self.t["alert"]}">●</span> desistiu &nbsp;&nbsp;·&nbsp;&nbsp; '
            'linha do tempo: azul = esta réplica, tracejado = média das réplicas, faixa rosada = pico. Clique ou arraste para ir a outro momento.')
        self._destacar()
        self.palco.tocar(tocando)

    def _play(self):
        sim = not self.palco.rodando
        self.palco.tocar(sim)
        self.btn_play.setText('❚❚  Pausar' if sim else '▶  Reproduzir')

    def _anim_mudou(self, k):
        s = self.saida
        if not s:
            return
        c = s['cfg']
        self.linha.definir(k)
        seg = (k + 1) * s['passo']
        if c['t0'] is not None:
            self.a_hora.setText((c['t0'] + timedelta(seconds=seg)).strftime('%H:%M:%S'))
        else:
            self.a_hora.setText(f'{int(seg // 60)}:{int(seg % 60):02d}')
        m = min(int(max(k, 0) * s['passo'] / 60), c['T'] - 1)
        pk = c['pico'][m]
        self.a_fase.setText(f'pico · λ {br(s["lams"][m])}/min' if pk else f'calma · λ {br(s["lams"][m])}/min')
        self.a_fase.setProperty('papel', 'selo-pico' if pk else 'selo-calma')
        repolir(self.a_fase)
        p = self.palco
        self.a_nums['esp'].setText(str(len(p.fila)))
        self.a_nums['cat'].setText(str(sum(1 for a in p.cats if a)))
        self.a_nums['cheg'].setText(str(p.contagem(1)))
        self.a_nums['pass'].setText(str(p.contagem(2)))
        self.a_nums['des'].setText(str(p.contagem(3)))
        self.a_nums['abertas'].setText(str(p.catracas_no_passo(k)))

    def closeEvent(self, ev):
        if self.rodada and self.rodada.isRunning():
            self.rodada.requestInterruption()
            self.rodada.wait(5000)
        super().closeEvent(ev)


def main():
    ac.configurar_utf8()
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName('Simulador da fila da catraca')
    from PySide6.QtCore import QLocale
    QLocale.setDefault(QLocale(QLocale.Portuguese, QLocale.Brazil))  # vírgula decimal nos campos
    matplotlib.rcParams['font.family'] = _fonte_mpl()
    matplotlib.rcParams['axes.unicode_minus'] = False
    arquivos = [a for a in sys.argv[1:] if not a.startswith('-')]
    jan = Janela(arquivos)
    jan.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
