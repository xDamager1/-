import sys
from typing import List, Tuple, Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QGraphicsScene, QGraphicsView, QGraphicsRectItem,
    QMessageBox, QDialog, QLabel
)

from PySide6.QtCore import Qt, QRunnable, QThreadPool, Signal, QObject
from PySide6.QtGui import QPen, QColor

Coord = Tuple[int, int]

# Ходы пони: конь + верблюд
PONY_MOVES = (
    (1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1),
    (1, 3), (3, 1), (-1, 3), (-3, 1), (1, -3), (3, -1), (-1, -3), (-3, -1)
)


class Board:
    """Класс, представляющий шахматную доску с размещенными пони."""

    def __init__(self, size: int, occupied: List[Coord] = None):
        if occupied is None:
            occupied = []
        self.size = size
        self.occupied = list(occupied)

    def attacked_positions(self) -> List[Coord]:
        """
        Возвращает список атакованных позиций на доске.

        :return: Список координат (x, y), находящихся под атакой размещенных пони.
        """
        attacks = set()

        for x0, y0 in self.occupied:
            for dx, dy in PONY_MOVES:
                x, y = x0 + dx, y0 + dy

                if 0 <= x < self.size and 0 <= y < self.size:
                    attacks.add((x, y))

        return list(attacks)

    def is_safe(self, pos: Coord) -> bool:
        """
        Проверяет, безопасна ли позиция для размещения нового пони.

        :param pos: Координаты (x, y) для проверки

        :return: True если позиция безопасна, False в противном случае

        """
        if pos in self.occupied:
            return False

        for occ in self.occupied:
            dx = abs(pos[0] - occ[0])
            dy = abs(pos[1] - occ[1])

            if (dx, dy) in [(1, 2), (2, 1), (1, 3), (3, 1)]:
                return False

        return True

    def place(self, pos: Coord):
        """
        Размещает пони на доске, если позиция безопасна.

        :param pos: Координаты (x, y) для размещения

        """
        if self.is_safe(pos):
            self.occupied.append(pos)


# Бэктрекинг для поиска одного решения

def find_one_solution(initial_coords: List[Coord], N: int, L: int) -> Optional[List[Coord]]:
    """
    Находит одно решение для размещения L пони на доске NxN с начальными координатами.

    :param initial_coords: Начальные координаты размещенных пони

    :param N: Размер доски

    :param L: Количество дополнительных пони для размещения

    :return: Список координат дополнительных пони или None, если решение не найдено

    """
    solution: List[Coord] = []

    def backtrack(start: int, need: int, occ: List[Coord]) -> bool:
        if need == 0:
            solution.extend(occ[len(initial_coords):])
            return True

        for i in range(start, N * N):
            x, y = divmod(i, N)

            if Board(N, occ).is_safe((x, y)):
                occ.append((x, y))

                if backtrack(i + 1, need - 1, occ):
                    return True

                occ.pop()

        return False

    occ_copy = initial_coords.copy()
    if backtrack(0, L, occ_copy):
        return solution

    return None


class WorkerSignals(QObject):
    """Сигналы для работы воркера."""
    finished = Signal(object)


class SolveRunnable(QRunnable):
    """Задача для выполнения поиска решения в отдельном потоке."""

    def __init__(self, initial: List[Coord], N: int, L: int):
        super().__init__()

        self.initial = initial
        self.N = N
        self.L = L
        self.signals = WorkerSignals()

    def run(self):
        """Выполняет поиск решения и испускает сигнал с результатом."""
        result = find_one_solution(self.initial, self.N, self.L)
        self.signals.finished.emit(result)


class CoordInputDialog(QDialog):
    """Диалоговое окно для ввода координат пони."""

    def __init__(self, K: int, board_size: int, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Ввод координат")
        self.setModal(True)
        self.coords: List[Coord] = []
        self.fields = []
        layout = QVBoxLayout()

        for i in range(K):
            row = QHBoxLayout()
            label = QLabel(f"Фигура {i + 1}:")
            line = QLineEdit()
            line.setPlaceholderText("x y")

            row.addWidget(label)
            row.addWidget(line)

            layout.addLayout(row)
            self.fields.append(line)
            line.textChanged.connect(self.validate)

        btn_layout = QHBoxLayout()
        self.btnOk = QPushButton("OK")
        self.btnOk.setEnabled(False)

        btnCancel = QPushButton("Отмена")

        btn_layout.addWidget(self.btnOk)
        btn_layout.addWidget(btnCancel)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.btnOk.clicked.connect(self.accept)
        btnCancel.clicked.connect(self.reject)

        self.board_size = board_size

    def validate(self):
        """Проверяет валидность введенных координат."""
        valid = True
        tmp: List[Coord] = []

        for line in self.fields:
            text = line.text().strip()
            try:
                x, y = map(int, text.split())
                if not (0 <= x < self.board_size and 0 <= y < self.board_size):
                    valid = False

                tmp.append((x, y))
            except:
                valid = False

        if valid:
            for i in range(len(tmp)):
                for j in range(i + 1, len(tmp)):
                    dx = abs(tmp[i][0] - tmp[j][0])
                    dy = abs(tmp[i][1] - tmp[j][1])

                    if (dx, dy) in [(1, 2), (2, 1), (1, 3), (3, 1)]:
                        valid = False
                        break

                if not valid:
                    break

        self.btnOk.setEnabled(valid)

    def accept(self):
        """Обрабатывает подтверждение ввода координат."""
        self.coords = [tuple(map(int, line.text().split())) for line in self.fields]
        super().accept()


class BoardWindow(QMainWindow):
    """Окно для отображения шахматной доски с пони."""

    def __init__(self, board: Board, auto: List[Coord]):
        super().__init__()

        self.setWindowTitle("Доска")
        self.board = board
        self.auto = auto
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.setCentralWidget(self.view)

        self.draw_board()

    def draw_board(self):
        """Отрисовывает доску с пони и атакованными позициями."""
        N = self.board.size
        cell = 30
        pen = QPen(Qt.black)

        # рисуем сетку
        for i in range(N):
            for j in range(N):
                rect = QGraphicsRectItem(j * cell, i * cell, cell, cell)
                rect.setPen(pen)
                rect.setBrush(Qt.white)

                self.scene.addItem(rect)

        # атакованные клетки
        pen_attack = QPen(QColor(255, 0, 0), 2)
        brush_attack = QColor(255, 200, 200, 100)
        for x, y in self.board.attacked_positions():
            rect = QGraphicsRectItem(y * cell, x * cell, cell, cell)
            rect.setPen(pen_attack)
            rect.setBrush(brush_attack)

            self.scene.addItem(rect)

        # пользовательские пони
        for x, y in self.board.occupied:
            rect = QGraphicsRectItem(y * cell, x * cell, cell, cell)
            rect.setBrush(Qt.blue)
            rect.setPen(pen)

            self.scene.addItem(rect)

        # автоматически расставленные пони
        for x, y in self.auto:
            rect = QGraphicsRectItem(y * cell, x * cell, cell, cell)
            rect.setBrush(Qt.red)
            rect.setPen(pen)

            self.scene.addItem(rect)


class MainWindow(QMainWindow):
    """Главное окно приложения для размещения пони."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Размещение пони")
        self.resize(400, 300)
        self.user_coords: List[Coord] = []
        self.board_window: Optional[BoardWindow] = None
        self.thread_pool = QThreadPool.globalInstance()

        # поля ввода
        self.inputN = QLineEdit();
        self.inputL = QLineEdit();
        self.inputK = QLineEdit()
        self.inputN.setPlaceholderText("Размер доски N")
        self.inputL.setPlaceholderText("Автопони L")
        self.inputK.setPlaceholderText("Польз. пони K")

        # кнопки
        self.btnCoords = QPushButton("Координаты");
        self.btnDraw = QPushButton("Отрисовать");
        self.btnExit = QPushButton("Выход")
        self.btnCoords.setEnabled(False);
        self.btnDraw.setEnabled(False)

        # слой
        layout = QVBoxLayout()
        for w in [self.inputN, self.inputL, self.inputK, self.btnCoords, self.btnDraw, self.btnExit]:
            layout.addWidget(w)

        container = QWidget();
        container.setLayout(layout)
        self.setCentralWidget(container)

        # сигналы
        for inp in [self.inputN, self.inputL, self.inputK]:
            inp.textChanged.connect(self.validate)

        self.btnCoords.clicked.connect(self.open_coords_dialog)
        self.btnDraw.clicked.connect(self.start_search)
        self.btnExit.clicked.connect(self.close)

    def validate(self):
        """Проверяет валидность введенных параметров."""
        N_ok = self.inputN.text().isdigit()
        L_ok = self.inputL.text().isdigit()
        K_ok = self.inputK.text().isdigit()

        if N_ok and L_ok and K_ok:
            N = int(self.inputN.text());
            K = int(self.inputK.text())

            self.btnCoords.setEnabled(K > 0)
            self.btnDraw.setEnabled(K == 0 or len(self.user_coords) == K)
        else:
            self.btnCoords.setEnabled(False)
            self.btnDraw.setEnabled(False)

    def open_coords_dialog(self):
        """Открывает диалог ввода координат пользовательских пони."""
        K = int(self.inputK.text());
        N = int(self.inputN.text())
        dlg = CoordInputDialog(K, N, self)

        if dlg.exec() == QDialog.Accepted:
            self.user_coords = dlg.coords

        self.validate()

    def start_search(self):
        """Запускает поиск решения в отдельном потоке."""
        N = int(self.inputN.text());
        L = int(self.inputL.text())
        initial = self.user_coords.copy()
        self.btnDraw.setEnabled(False)

        worker = SolveRunnable(initial, N, L)
        worker.signals.finished.connect(self.on_search_finished)

        self.thread_pool.start(worker)

    def on_search_finished(self, solution: Optional[List[Coord]]):
        """
        Обрабатывает завершение поиска решения.

        :param solution: Найденное решение или None, если решение не найдено

        """
        if solution is None:
            QMessageBox.warning(self, "Ошибка", "Нет решений для L пони")
            self.btnDraw.setEnabled(True)
            return

        N = int(self.inputN.text())
        board = Board(N, self.user_coords.copy())

        for coord in solution:
            board.place(coord)

        self.board_window = BoardWindow(board, solution)
        self.board_window.show()
        self.btnDraw.setEnabled(True)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec())
