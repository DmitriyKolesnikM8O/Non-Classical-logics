# Описание программного интерфейса (API)

Документ адресован разработчику, который использует библиотеку проекта в своей
программе. Описаны три пакета:

| Пакет | Назначение | Внешние зависимости |
| --- | --- | --- |
| `fuzzy_core` | нечеткие величины, арифметика, сравнение, генерация выборки, кластеризация | нет (только стандартная библиотека) |
| `logger` | журналирование сессии в текстовый файл | нет |
| `gui` | графический интерфейс (окно, вкладки, графики) | `tkinter`, `matplotlib` |

Пакеты `fuzzy_core` и `logger` не зависят от `gui`: библиотеку можно
использовать в консольных программах, скриптах и серверных задачах.

---

## 1. Установка и импорт

Проект оформлен как устанавливаемый пакет (`pyproject.toml`, src-layout):

```bat
.venv\Scripts\python.exe -m pip install -e .
```

После этого пакеты доступны из любого места:

```python
from fuzzy_core import UniformFuzzyVariable, FuzzySet, generate_sample, kmeans
from logger import SessionLogger
```

Требуется Python 3.10 или новее. Графический интерфейс дополнительно требует
`matplotlib` (он указан в `requirements.txt` вместе с `numpy`).

---

## 2. Быстрый старт

Полный рабочий пример: создать величины, выполнить операции, сравнить,
сгенерировать выборку, кластеризовать её и записать всё в журнал.

```python
from fuzzy_core import UniformFuzzyVariable, generate_sample, kmeans, cluster
from logger import SessionLogger, describe_variable

a = UniformFuzzyVariable(1, 3)
b = UniformFuzzyVariable(2, 5)

print((a + b).support)          # (3.0, 8.0)
print(a.distance(b))            # 2.0
print(round(a.dominance(b), 4)) # 0.0833
print(a < b, describe_variable(a))   # True [1.000, 3.000] (c=2.000, w=2.000)

sample = generate_sample(150, seed=2026)
result = kmeans(sample, 5, seed=2026)
print(result.sizes)             # [31, 41, 27, 29, 22]
print(round(result.silhouette(), 4))  # 0.4516

by_threshold = cluster(sample, "threshold", threshold=5.0)
print(len(by_threshold.clusters))     # 7

with SessionLogger(log_dir="logs") as log:
    log.log_sample(sample, seed=2026)
    log.log_clustering(result)
    print(log.log_path)
```

Фрагмент полученного журнала:

```text
2026-10-17 17:39:14,812 | INFO | Выборка (генератор): элементов=150
2026-10-17 17:39:14,813 | INFO |     seed=2026
2026-10-17 17:39:14,813 | INFO |     охватывающий интервал=[-9.719, 13.316], средний центр=1.14971, средняя ширина=2.12264
2026-10-17 17:39:14,813 | INFO | Кластеризация: метод=kmeans, метрика=hausdorff, параметры: k=5, max_iter=100, tol=1e-06, seed=2026
2026-10-17 17:39:14,813 | INFO |     элементов=150, кластеров=5, точек-шума=0
2026-10-17 17:39:14,813 | INFO |     размеры кластеров=[31, 41, 27, 29, 22]
2026-10-17 17:39:14,815 | INFO |     суммарная инерция=425.218, средняя внутрикластерная дисперсия центров=1.48066, максимальный диаметр=6.52878
2026-10-17 17:39:14,833 | INFO |     средний силуэт=0.4516
2026-10-17 17:39:14,833 | INFO |     Кластер 1: размер=31, центроид=[-7.387, -5.618] (c=-6.502, w=1.769), инерция=111.024, дисперсия центров=2.06711, диаметр=6.52878
```

---

## 3. Пакет `fuzzy_core`

### 3.1. Исключения

| Исключение | Базовый класс | Когда возбуждается |
| --- | --- | --- |
| `FuzzyVariableError` | `ValueError` | неверные границы величины или параметры α-среза, деление на интервал с нулём |
| `FuzzySetError` | `ValueError` | некорректные операции над множеством величин |

Так как оба класса наследуют `ValueError`, достаточно перехватывать
`ValueError`. При передаче аргумента неподходящего типа возбуждается `TypeError`.

### 3.2. Класс `UniformFuzzyVariable`

```python
UniformFuzzyVariable(a: float, b: float)
```

Нечеткая величина с равномерной функцией принадлежности: `μ(x) = 1` при
`a ≤ x ≤ b` и `0` иначе. Требуется `a ≤ b`; оба числа должны быть конечными.

**Альтернативные конструкторы**

| Метод | Описание |
| --- | --- |
| `UniformFuzzyVariable.from_center_width(center, width)` | величина с заданными центром и шириной; `width ≥ 0` |

**Свойства**

| Свойство | Тип | Значение |
| --- | --- | --- |
| `a`, `b` | `float` | границы носителя |
| `center`, `c` | `float` | `(a + b) / 2` |
| `width`, `w` | `float` | `b − a` |
| `support` | `tuple` | носитель `(a, b)` |
| `core` | `tuple` | ядро `(a, b)` (для равномерной величины совпадает с носителем) |
| `is_crisp` | `bool` | `True`, если `a == b` (вырожденная величина) |

**Функция принадлежности**

| Метод | Описание |
| --- | --- |
| `membership(x)` | `1.0`, если `a ≤ x ≤ b`, иначе `0.0` |
| `mu(x)` | синоним `membership(x)` |
| `alpha_cut(alpha=1.0)` | α-срез `{x : μ(x) ≥ alpha}`: для равномерной величины — `(a, b)` при `0 < alpha ≤ 1` и `()` при `alpha > 1` |
| `a(x)` | вызов объекта как функции: `a(2)` равносильно `a.membership(2)` |

**Арифметические операции.** Операндом может быть другая величина или число
(число трактуется как вырожденная величина `[x, x]`). Поддерживаются также
обращённые операции (`2 + a`, `5 - a`, `2 * a`, `4 / a`) и унарный минус.

| Выражение | Результат | Правило |
| --- | --- | --- |
| `a + b` | величина | `[a₁ + a₂, b₁ + b₂]` |
| `a - b` | величина | `[a₁ − b₂, b₁ − a₂]` |
| `a * b` | величина | `[min P, max P]`, `P = {a₁a₂, a₁b₂, b₁a₂, b₁b₂}` |
| `a / b` | величина | `a * [1/b₂, 1/a₂]`; `FuzzyVariableError`, если `0 ∈ [a₂, b₂]` |
| `-a` | величина | `[-b, -a]` |

**Метрики и сравнение**

| Метод | Результат |
| --- | --- |
| `hausdorff_distance(other)` | `max(|a₁ − a₂|, |b₁ − b₂|)` |
| `euclidean_distance(other)` | `√(((a₁ − a₂)² + (b₁ − b₂)²) / 2)` |
| `distance(other, metric="hausdorff")` | расстояние по имени метрики |
| `rank_key()` | пара `(center, width)` |
| `compare(other)` | `-1`, `0` или `1` — результат лексикографического сравнения по `(c, w)` |
| `possibility_greater_or_equal(other)` | индекс возможности `Pos(A ≥ B)`: 1, если `b₁ ≥ a₂`, иначе 0 |
| `necessity_greater_or_equal(other)` | индекс необходимости `Nec(A ≥ B)`: 1, если `a₁ ≥ b₂`, иначе 0 |
| `dominance(other)` | вероятность `P(X_A > X_B)` для равномерных значений в носителях, `[0, 1]` |

**Операторы сравнения** (`<`, `<=`, `>`, `>=`) используют `rank_key()`, то есть
сначала сравнивают центры, а при их равенстве — ширины. Их можно применять и к
числам: `a < 2.5`.

**Прочие методы**

| Метод | Описание |
| --- | --- |
| `__iter__` | распаковка в границы: `lo, hi = a` |
| `__eq__` | точное равенство границ (с числом не сравнивается) |
| `__hash__` | величина может быть ключом словаря или элементом множества |
| `__repr__` | `UniformFuzzyVariable(a=1, b=3)` |

**Пример**

```python
from fuzzy_core import UniformFuzzyVariable as V

a, b = V(1, 3), V(2, 5)
a + b            # UniformFuzzyVariable(a=3, b=8)
a - b            # UniformFuzzyVariable(a=-4, b=1)
a * b            # UniformFuzzyVariable(a=2, b=15)
a / b            # UniformFuzzyVariable(a=0.2, b=1.5)
2 * a            # UniformFuzzyVariable(a=2, b=6)
-a               # UniformFuzzyVariable(a=-3, b=-1)
a.distance(b)            # 2.0
a.distance(b, "euclidean")   # 1.5811388300841898
a.dominance(b)           # 0.08333333333333333
a.compare(b)             # -1
V.from_center_width(5, 2)    # UniformFuzzyVariable(a=4, b=6)

try:
    a / V(-1, 1)
except Exception as exc:
    print(exc)   # Деление невозможно: интервал делителя [-1, 1] содержит 0
```

**α-срезы других форм функции принадлежности.** Модульные функции (экспортируются
из `fuzzy_core`):

```python
alpha_cut_trapezoid(a, c, d, b, alpha=1.0) -> tuple
alpha_cut_triangular(a, m, b, alpha=1.0) -> tuple
```

| Функция | Описание |
| --- | --- |
| `alpha_cut_trapezoid` | α-срез трапеции `T(a, c, d, b)`: `(a + α(c − a), b − α(b − d))`; при `α = 1` — плато `(c, d)`, при `α > 1` — `()` |
| `alpha_cut_triangular` | α-срез треугольника `T(a, m, b)` — частный случай трапеции при `c = d = m`: `(a + α(m − a), b − α(b − m))` |

Требуется `a ≤ c ≤ d ≤ b` (для треугольника `a ≤ m ≤ b`), все параметры должны
быть конечными, `0 < alpha ≤ 1`; иначе возбуждается `FuzzyVariableError`.
Равномерная величина варианта 1 — вырожденная трапеция с `c = a`, `d = b`,
поэтому `alpha_cut_trapezoid(a, a, b, b, α) == (a, b)` при любом `α` — то же
самое, что `UniformFuzzyVariable.alpha_cut(α)`.

```python
from fuzzy_core import alpha_cut_triangular, alpha_cut_trapezoid, UniformFuzzyVariable as V

alpha_cut_triangular(0, 5, 10, 0.5)      # (2.5, 7.5)
alpha_cut_triangular(0, 5, 10, 1.0)      # (5.0, 5.0)
alpha_cut_trapezoid(0, 2, 8, 10, 0.5)    # (1.0, 9.0)
alpha_cut_trapezoid(1, 1, 3, 3, 0.7)     # (1.0, 3.0) — вырожденная трапеция
V(1, 3).alpha_cut(0.7)                   # (1.0, 3.0)
```

### 3.3. Класс `FuzzySet`

```python
FuzzySet(variables: Iterable[object] = ())
```

Упорядоченная коллекция величин (порядок добавления сохраняется). Числа,
переданные вместо величин, автоматически превращаются в вырожденные величины
`[x, x]`.

**Коллекция**

| Метод | Описание |
| --- | --- |
| `len(s)` | число элементов |
| `s[i]`, `s[i:j]` | элемент или срез |
| `x in s` | проверка наличия |
| `for v in s` | обход элементов |
| `append(v)`, `insert(i, v)`, `extend(iterable)` | добавление |
| `remove(v)`, `pop(i=-1)`, `clear()` | удаление |
| `unique()` | новое множество без дубликатов (порядок сохраняется) |
| `s + other` | объединение: множество, список или отдельная величина |

**Отбор и статистика**

| Метод | Описание |
| --- | --- |
| `find(predicate)` | первая величина, удовлетворяющая условию, или `None` |
| `filter(predicate)` | новое множество из подходящих величин |
| `filter_by_center(low=None, high=None)` | отбор по центру (границы включаются, `None` — без ограничения) |
| `filter_by_width(low=None, high=None)` | отбор по ширине |
| `sorted_by_rank(reverse=False)` | новое множество, отсортированное по `(c, w)` |
| `min_by_rank()`, `max_by_rank()` | минимальная и максимальная величина |
| `mean_center()`, `mean_width()` | средние центр и ширина |
| `envelope()` | охватывающий интервал `(min a, max b)` |

**Расстояния**

| Метод | Описание |
| --- | --- |
| `distances_to(v, metric="hausdorff")` | список расстояний до величины `v` |
| `nearest(v, metric="hausdorff")` | ближайшая величина или `None` для пустого множества |
| `distance_matrix(metric="hausdorff")` | матрица попарных расстояний |

**Пример**

```python
from fuzzy_core import FuzzySet, UniformFuzzyVariable as V

s = FuzzySet([V(1, 3), V(2, 5), 7])
len(s)                      # 3
s[-1]                       # UniformFuzzyVariable(a=7, b=7)
s.nearest(V(1.2, 3.2))      # UniformFuzzyVariable(a=1, b=3)
s.envelope()                # (1.0, 7.0)
s.filter_by_width(low=3)    # FuzzySet из одной величины [2, 5]
s.distance_matrix()[0]      # [0.0, 2.0, 6.0]
len(s.unique())             # 3
len(s + V(9, 9))            # 4
```

### 3.4. Метрики расстояния

| Функция | Описание |
| --- | --- |
| `hausdorff_distance(first, second)` | расстояние Хаусдорфа |
| `euclidean_distance(first, second)` | евклидово расстояние между границами |
| `get_distance_function(metric="hausdorff")` | функция по имени метрики |
| `DISTANCE_METRICS` | словарь доступных метрик: `{"hausdorff": ..., "euclidean": ...}` |

Операндами могут быть величины и числа. Если имя метрики неизвестно,
возбуждается `ValueError: Неизвестная метрика 'имя'. Доступны: euclidean, hausdorff`.

Свою метрику можно зарегистрировать в словаре:

```python
from fuzzy_core import DISTANCE_METRICS, UniformFuzzyVariable as V

def center_distance(first, second):
    first = first if isinstance(first, V) else V(first, first)
    second = second if isinstance(second, V) else V(second, second)
    return abs(first.center - second.center)

DISTANCE_METRICS["center"] = center_distance
V(1, 3).distance(V(2, 5), "center")   # 1.5
```

### 3.5. Генератор выборки

```python
generate_sample(count=None, *, seed=None, a_range=(-10.0, 10.0),
                width_range=(0.0, 4.0), count_range=(100, 300)) -> FuzzySet
generate_variables(rng, count, a_range=(-10.0, 10.0), width_range=(0.0, 4.0))
                -> List[UniformFuzzyVariable]
```

| Параметр | Смысл |
| --- | --- |
| `count` | число величин; `None` — выбрать случайно из `count_range` |
| `seed` | зерно генератора (число или строка); одинаковое зерно и одинаковые параметры дают одинаковую выборку |
| `a_range` | диапазон левой границы `a` |
| `width_range` | диапазон ширины `w`; правая граница `b = a + w` |
| `count_range` | допустимый диапазон объёма выборки |

Возвращается `FuzzySet`. Явно заданный `count` должен попадать в `count_range`,
иначе возбуждается `ValueError`; чтобы получить, например, 50 величин, нужно
расширить диапазон: `generate_sample(50, count_range=(50, 50))`. Дробный `count`
даёт `TypeError`.

**Замечание о воспроизводимости.** Если `count` не задан, объём выбирается
первым обращением к генератору, поэтому поток случайных чисел сдвигается на один
шаг. Следствие: при одном и том же зерне выборки `generate_sample(150, seed=2026)`
и `generate_sample(seed=2026, count_range=(150, 150))` **различаются**. Чтобы
повторить выборку, созданную в интерфейсе программы, передавайте тот же
`count_range`, что был задан в полях «Объём выборки».

```python
generate_sample(3, count_range=(3, 3), seed=7)
# FuzzySet из трёх величин, воспроизводимо
```

**Константы:** `MIN_COUNT = 100`, `MAX_COUNT = 300`,
`DEFAULT_COUNT_RANGE = (100, 300)`, `DEFAULT_A_RANGE = (-10.0, 10.0)`,
`DEFAULT_WIDTH_RANGE = (0.0, 4.0)`.

### 3.6. Кластеризация

```python
kmeans(variables, k, *, metric="hausdorff", seed=None, max_iter=100, tol=1e-06)
threshold_clustering(variables, *, threshold, metric="hausdorff")
alpha_cut_clustering(variables, *, alpha=0.5, metric="hausdorff", linkage="single", closure=True, scale=None)
alpha_cut_profile(variables, alphas=None, *, metric="hausdorff", linkage="single", closure=True, scale=None)
similarity_matrix(variables, *, metric="hausdorff", scale=None)
max_min_closure(similarity)
density_clustering(variables, *, eps, min_points=2, metric="hausdorff")
agglomerate(variables, *, metric="hausdorff")
grouped_result(variables, labels, *, method, metric="hausdorff", parameters=None)
cluster(variables, method="kmeans", *, metric="hausdorff", **parameters)

AlphaClusterer(variables, *, metric="hausdorff", linkage="single", closure=True, scale=None)
Agglomeration(size, merges=())
Merge(step, left, right, height, cluster_count, members)
```

**Общие соглашения**

- `variables` — `FuzzySet`, список или любой итерируемый объект; числа
  приводятся к вырожденным величинам;
- `metric` — имя метрики из `DISTANCE_METRICS`;
- возвращается `ClusterResult`;
- кластеры нумеруются детерминированно: по возрастанию центра центроида, а при
  равенстве — по возрастанию его ширины; метки кластеров — `0 … K−1`, шум — `NOISE_LABEL = -1`.

**Методы**

| Метод | Параметры и смысл |
| --- | --- |
| `kmeans` | `k` — число кластеров, `seed` — зерно инициализации k-means++, `max_iter` — лимит итераций, `tol` — порог стабилизации центроидов |
| `threshold_clustering` | `threshold` — максимальное допустимое расстояние внутри кластера (агломеративный алгоритм с полной связью) |
| `alpha_cut_clustering` | `alpha` — уровень отбора из `(0, 1]` по шкале сходства `r_ij = 1 − d_ij/d0`; `linkage` — `"single"` (канонический α-срез: компоненты связности) или `"complete"` (разрез дендрограммы полной связи); `closure` — предварительное max-min замыкание (только для `"single"`); `scale` — масштаб `d0` (по умолчанию максимум расстояния в выборке) |
| `alpha_cut_profile` | `alphas` — сетка уровней (по умолчанию `1.0, 0.9, …, 0.1`); возвращает список `{"alpha": уровень, "cluster_count": k}` |
| `similarity_matrix` | матрица сходства `r_ij = 1 − d_ij/d0` со значениями из `[0, 1]`, `r_ii = 1` |
| `max_min_closure` | max-min транзитивное замыкание матрицы сходства — нечёткое отношение эквивалентности |
| `density_clustering` | `eps` — радиус окрестности, `min_points` — минимум точек в окрестности (включая саму точку) |
| `agglomerate` | строит трассу агломерации полной связи (`Agglomeration`) для выборки — без разреза по порогу; удобно для пошагового просмотра |
| `grouped_result` | собирает `ClusterResult` из готовых меток (например, разрез трассы на шаге `step`); метки `NOISE_LABEL` считаются шумом |
| `cluster` | `method` — `"kmeans"`, `"threshold"`, `"alpha"` или `"density"`; остальные именованные аргументы передаются выбранному методу |
| `AlphaClusterer` | движок α-кластеризации: матрица сходства считается при создании объекта, замыкание и трасса агломерации — лениво и однократно. Методы: `clustering(alpha, *, closure=None) -> ClusterResult`, `profile(alphas=None, *, closure=None) -> list`, свойства `size`, `scale`, `similarity`, `closed`, `trace` |
| `Agglomeration` | трасса агломерации полной связи: `size` — число величин, `merges` — кортеж `(i, j, высота)`; свойства `heights`; методы `labels(threshold)`, `cluster_count(threshold)`, `cut_step(threshold)`, `labels_after(step)`, `cluster_count_after(step)`, `groups_after(step)`, `steps()` |

**Ошибки**

| Ситуация | Сообщение |
| --- | --- |
| `k = 0` | `k должно быть >= 1, получено 0` |
| `k` больше числа величин | `k должно удовлетворять 1 <= k <= 2, получено 5` |
| `max_iter = 0` | `max_iter должен быть целым числом >= 1, получено 0` |
| отрицательный порог | `threshold не может быть отрицательным, получено -1` |
| `eps = 0` | `eps должен быть больше нуля, получено 0` |
| `min_points = 0` | `min_points должен быть целым числом >= 1, получено 0` |
| неизвестный метод | `Неизвестный метод кластеризации 'нет'. Доступны: alpha, density, kmeans, threshold` |
| `alpha = 0` или `alpha > 1` | `α-уровень должен лежать в (0, 1], получено 1.5` |
| неизвестный тип связи | `Неизвестный тип связи 'average'. Доступны: single, complete` |
| отрицательный или нулевой `scale` | `масштаб расстояний должен быть положительным числом, получено 0` |
| неизвестная метрика | `Неизвестная метрика 'манхэттен'. Доступны: euclidean, hausdorff` |

Пустой набор данных не является ошибкой: `kmeans([], 1)` возвращает результат с
нулевым числом кластеров.

**Пример: кластеризация по α-уровню**

```python
from fuzzy_core import alpha_cut_clustering, alpha_cut_profile, generate_sample

sample = generate_sample(150, seed=2026)

result = alpha_cut_clustering(sample, alpha=0.7, linkage="complete")
len(result.clusters)            # 5
result.parameters               # {'alpha': 0.7, 'linkage': 'complete', 'closure': False, ...}

[(p["alpha"], p["cluster_count"]) for p in alpha_cut_profile(sample, linkage="complete")]
# [(1.0, 150), (0.9, 20), (0.8, 8), (0.7, 5), (0.6, 4), (0.5, 3), (0.4, 2), ...]
```

Число кластеров не убывает с ростом `alpha`: `alpha = 1` оставляет только
совпадающие величины, малое `alpha` сливает всё в один кластер.

**Пример: перебор уровней без повторных вычислений (движок `AlphaClusterer`)**

Движок нужен там, где уровень перебирается многократно (ползунок α в интерфейсе,
анимация): тяжёлые матрицы считаются один раз, а каждый следующий уровень стоит
доли миллисекунды.

```python
from fuzzy_core import AlphaClusterer, generate_sample

sample = generate_sample(300, seed=42)
engine = AlphaClusterer(sample, linkage="complete")

engine.clustering(0.8).sizes        # кластеры при α = 0.8
engine.profile([1.0, 0.8, 0.5])     # [{'alpha': 1.0, 'cluster_count': 300}, ...]
engine.similarity                   # матрица сходства r_ij (копия)
engine.trace.cluster_count((1 - 0.8) * engine.scale)   # 9
engine.trace.labels((1 - 0.8) * engine.scale)          # метки кластеров
```

`AlphaClusterer.clustering(alpha)` и `AlphaClusterer.profile(...)` дают ровно те же
результаты, что `alpha_cut_clustering` / `alpha_cut_profile`. Свойство `closed`
(замыкание) считается при первом обращении и не нужно при `linkage="complete"`;
свойство `trace` (трасса агломерации) — наоборот, нужно только для
`linkage="complete"`. Разрез трассы по порогу `τ` эквивалентен
`threshold_clustering(threshold=τ)`.

**Пример: пошаговая агломерация**

Трасса хранит процесс полностью, поэтому его можно «проиграть» слияние за
слиянием, не пересчитывая матрицу расстояний.

```python
from fuzzy_core import agglomerate, grouped_result, generate_sample

sample = generate_sample(40, seed=7)
trace = agglomerate(sample)

trace.size                       # 40
len(trace.merges)                # 39 — столько слияний до одного кластера
trace.cluster_count_after(0)     # 40 — все точки отдельно
trace.labels_after(1)            # метки после первого слияния
trace.groups_after(1)            # группы индексов после первого слияния

for merge in trace.steps()[:3]:
    merge.describe()             # 'шаг 1: слияние кластеров размерами 1 и 1 на расстоянии 0.0137'
    merge.members                # исходные индексы объединённого кластера

# результат на произвольном шаге собирается из меток
result = grouped_result(sample, trace.labels_after(5), method="threshold",
                        parameters={"step": 5})
len(result.clusters)             # столько кластеров осталось после 5 слияний
```

Метод `labels_after(step)` — это разрез трассы после первых `step` слияний
(`step = 0` — исходное состояние, `step = len(merges)` — один кластер); он
согласован с разрезом по высоте: `labels_after(n)` совпадает с `labels(h_n)`.

**Класс `Merge`** — одно слияние процесса.

| Член | Описание |
| --- | --- |
| `step` | номер шага (с единицы) |
| `left`, `right` | исходные индексы элементов двух сливающихся кластеров |
| `height` | расстояние (высота дендрограммы) в момент слияния |
| `cluster_count` | число кластеров после слияния |
| `members` | объединённый состав кластера (все исходные индексы) |
| `member_count` | число элементов в объединённом кластере |
| `describe()` | короткое описание шага для журнала и подписи |

**Класс `Cluster`** — один кластер.

| Член | Описание |
| --- | --- |
| `size` | число элементов |
| `diameter` | максимальное расстояние между элементами |
| `inertia` | сумма квадратов расстояний до центроида |
| `center_variance` | дисперсия центров элементов |
| `to_dict()` | `size`, `centroid`, `center`, `center_variance`, `diameter`, `inertia`, `members` |

**Класс `ClusterResult`** — результат кластеризации.

| Член | Описание |
| --- | --- |
| `len(result)` | число кластеров |
| `result[i]` | кластер по индексу |
| `clusters` | список объектов `Cluster` |
| `labels` | метка кластера для каждого элемента (шум — `-1`) |
| `items` | исходные величины |
| `noise` | индексы шумовых точек |
| `method`, `metric`, `parameters` | метод, метрика и параметры запуска |
| `sizes` | размеры кластеров |
| `centroids` | центроиды кластеров |
| `total_inertia` | суммарная инерция |
| `average_center_variance` | средняя внутрикластерная дисперсия центров |
| `max_diameter` | максимальный диаметр |
| `silhouette()` | коэффициент силуэта или `None`, если кластер меньше двух |
| `points_by_cluster()` | списки величин по кластерам |
| `to_dict()` | представление результата простыми типами (для журнала) |

Ключи `to_dict()`: `method`, `metric`, `parameters`, `elements`,
`cluster_count`, `noise_count`, `sizes`, `centroids`, `diameters`, `inertias`,
`center_variances`, `total_inertia`, `average_center_variance`, `max_diameter`,
`silhouette`.

**Пример**

```python
from fuzzy_core import FuzzySet, generate_sample, kmeans, cluster

sample = generate_sample(120, seed=1)
result = kmeans(sample, 4, seed=1)
result.sizes                     # [31, 28, 29, 32]
result.silhouette()              # 0.4946 (число из [-1, 1])
result.labels[0]                 # метка первой величины

by_threshold = cluster(sample, "threshold", threshold=2.0)
by_density = cluster(sample, "density", eps=1.0, min_points=3)
by_density.noise                 # индексы шумовых точек
```

**Реестры:** `CLUSTERING_METHODS` — словарь
`{"kmeans": ..., "threshold": ..., "density": ...}`; `NOISE_LABEL = -1`.

---

## 4. Пакет `logger`

### 4.1. Класс `SessionLogger`

```python
SessionLogger(log_dir=None, filename=None, *, level=logging.INFO,
              echo=False, encoding="utf-8")
```

Журнал — обычный текстовый файл с временными метками. Если `log_dir` не задан,
используется `default_log_dir()` (папка `logs/` в корне проекта); если не задан
`filename`, имя формируется как `session_ГГГГ-ММ-ДД_ЧЧ-ММ-СС.log` по местному
времени запуска.

| Член | Описание |
| --- | --- |
| `log_path` | путь к файлу журнала (`pathlib.Path`) |
| `log_dir` | папка журналов |
| `closed` | `True`, если журнал закрыт |
| `debug/info/warning/error(message)` | произвольная запись |
| `log_error(message, details="")` | запись об ошибке |
| `session_started(note=None)`, `session_finished(note=None)` | рамка сессии |
| `log_variable(action, variable)` | величина с описанием `[a, b] (c=…, w=…)` |
| `log_variables(action, variables)` | набор величин с охватывающим интервалом |
| `log_operation(operation, left=None, right=None, result=None)` | арифметическая операция |
| `log_comparison(left, relation, right, outcome)` | результат сравнения |
| `log_dominance(left, right)` | степень доминирования |
| `log_sample(variables, *, source="генератор", seed=None, a_range=None, width_range=None, count_range=None)` | параметры и сводка выборки |
| `log_clustering(result, *, include_clusters=True)` | параметры и результаты кластеризации; `include_clusters=False` — без разбора по кластерам |
| `read()` | всё содержимое файла |
| `tail(lines=200)` | последние строки |
| `close()` | закрыть файл |

Класс поддерживает контекстный менеджер: при выходе из блока `with` журнал
закрывается автоматически. При `echo=True` записи дублируются в консоль.

```python
from logger import SessionLogger
from fuzzy_core import UniformFuzzyVariable

with SessionLogger("logs", echo=True) as log:
    log.session_started("демонстрация")
    log.log_operation("сложение", UniformFuzzyVariable(1, 3),
                      UniformFuzzyVariable(2, 5), UniformFuzzyVariable(3, 8))
    log.info("готово")
```

### 4.2. Вспомогательные функции и константы

| Объект | Описание |
| --- | --- |
| `default_log_dir()` | папка журналов по умолчанию |
| `format_variable(value, digits=3)` | `"[1.000, 3.000]"` |
| `describe_variable(variable, digits=3)` | `"[1.000, 3.000] (c=2.000, w=2.000)"` |
| `TIMESTAMP_FORMAT` | `"%Y-%m-%d %H:%M:%S"` — метки внутри журнала |
| `FILE_TIMESTAMP_FORMAT` | `"%Y-%m-%d_%H-%M-%S"` — метка в имени файла |

Функции форматирования принимают как величины, так и числа, и не зависят от
журнала — их удобно использовать в собственных отчётах.

---

## 5. Пакет `gui`

Пакет состоит из трёх модулей. Он опирается на `fuzzy_core` и `logger`, но не
наоборот; любой из модулей можно использовать отдельно.

### 5.1. `gui.plotter` — графики

```python
MembershipPlot(master, *, width=6.4, height=4.4, dpi=100, toolbar=True,
               title="Функции принадлежности μ(x)")
```

Виджет для встраивания в Tkinter-окно (внутри — `matplotlib.figure.Figure` и
`FigureCanvasTkAgg`, `pyplot` не используется). При `toolbar=True` добавляется
панель инструментов matplotlib (масштаб, сохранение картинки).

| Метод | Описание |
| --- | --- |
| `show_variables(variables, labels=None, *, title=None, pad=1.0, show_center=True, max_legend_items=10)` | рисует функции принадлежности; при числе кривых больше `max_legend_items` легенда на графике не рисуется |
| `show_scatter(points, groups, *, centroids=(), title=None, xlabel="центр c", ylabel="ширина w", max_legend_items=10)` | диаграмма рассеяния точек `(c, w)` с раскраской по номерам кластеров (`-1` — шум); центроиды рисуются ромбами |
| `show_alpha_profile(profile, *, current=None, title=None, xlabel="уровень отбора α", ylabel="число кластеров k(α)")` | кривая-ступенька `k(α)` по списку `{"alpha", "cluster_count"}`; `current` отмечает текущий уровень α вертикальной линией |
| `show_similarity_matrix(matrix, *, alpha=None, order=None, labels=None, title=None)` | тепловая карта матрицы сходства: `order` переставляет строки и столбцы (кластеры — блоками на диагонали), `labels` рисует границы блоков, клетки `r_ij ≥ alpha` подсвечиваются. `ValueError`, если матрица не квадратная или `order` не перестановка |
| `reset(title=None)` | очистить график |
| `redraw()` | перерисовать холст |
| `save(path, *, dpi=150)` | сохранить рисунок в файл |
| `curve_points(index)` | точки кривой по индексу (для проверок в тестах) |
| `curve_count`, `labels`, `x_limits` | число кривых, подписи, границы по оси X |
| `point_count`, `group_count`, `centroid_count` | число точек, групп и центроидов на диаграмме рассеяния |
| `group_colors`, `group_sizes` | цвета и размеры групп |
| `profile_points`, `current_alpha` | точки кривой `k(α)` (по возрастанию уровня) и отмеченный α |
| `matrix_size`, `matrix_alpha`, `matrix_order`, `matrix_values` | размер и уровень подсветки матрицы, порядок индексов и матрица в показанном виде |

Дополнительно: `distinct_colors(count)` — список различимых цветов (до 8 групп —
фиксированная палитра `COLORS`, дальше цвета строятся по кругу оттенков с шагом
«золотое сечение»); `membership_points(variable)` — точки контура функции
принадлежности (стороны прямоугольника, без нулевой линии вдоль оси x); `NOISE_COLOR` — цвет шума.

```python
import tkinter as tk
from gui.plotter import MembershipPlot
from fuzzy_core import UniformFuzzyVariable

root = tk.Tk()
plot = MembershipPlot(root)
plot.show_variables([UniformFuzzyVariable(1, 3), UniformFuzzyVariable(2, 5)],
                    labels=["A", "B"], title="A и B")
plot.pack(fill="both", expand=True)
root.mainloop()
```

### 5.2. `gui.widgets` — элементы интерфейса

| Класс или функция | Назначение |
| --- | --- |
| `LabeledEntry(master, label, *, value="", width=10)` | поле ввода с подписью: `text`, `set(value)`, `number()` |
| `Table(master, columns, *, height=18)` | таблица; `columns` — последовательность `(ключ, заголовок, ширина)`; `set_rows`, `add_row`, `row(i)`, `rows()`, `row_count`, `clear()` |
| `ProtocolView(master, *, title="", height=10, wrap="word")` | текстовое поле протокола: `content`, `append`, `append_many`, `set_text`, `clear()` |
| `LegendPanel(master, *, title="Легенда", width=230)` | прокручиваемая панель легенды: `set_items([(цвет, подпись, пояснение), …])`, `item_count`, `captions`, `clear()` |
| `StatusBar(master, message="Готово", log_path=None)` | строка состояния: `message`, `log_text`, `set_message`, `set_log_path` |
| `PlaceholderTab(master, title, description="", hints=None)` | заглушка вкладки с описанием |
| `parse_number(text, *, name="значение")` | разбор числа из поля ввода (принимается и точка, и запятая); `ValueError` с понятным текстом при ошибке |
| `center_window(window, width, height)` | разместить окно по центру экрана |

### 5.3. `gui.app` — приложение

```python
FuzzyApp(master=None, *, logger=None, log_dir=None)
```

Главное окно с четырьмя вкладками. Если `logger` не передан, создаётся
`SessionLogger` с папкой `log_dir`.

| Член | Описание |
| --- | --- |
| `tabs` | словарь «название вкладки → объект вкладки» |
| `logger` | используемый журнал |
| `sample`, `sample_seed`, `sample_parameters` | текущая выборка и её параметры |
| `clustering_result` | результат последней кластеризации |
| `status_bar` | строка состояния |
| `run()` | запустить главный цикл Tkinter и вернуть код выхода |
| `close()` | закрыть журнал и окно |
| `closed` | `True`, если окно закрыто |
| `set_status(text)` | показать сообщение в строке состояния |
| `remember_sample(sample, seed=None, parameters=None)` | передать выборку вкладке кластеризации |
| `get_sample()` | получить текущую выборку |
| `remember_clustering(result)` | сохранить результат кластеризации |
| `open_log_dir()` | открыть папку журналов в проводнике |
| `show_about()` | окно «О программе» |

**Вкладки** (классы доступны для повторного использования):

| Класс | Ключевые методы |
| --- | --- |
| `ArithmeticTab(master, logger, *, on_message=None)` | `compute(operation)`, `compare()`, `variable_a()`, `variable_b()`, `clear_protocol()` |
| `GenerationTab(master, logger, *, on_message=None, on_sample=None)` | `read_parameters()`, `read_seed()`, `generate()`, `fill_table()`, `clear()` |
| `ClusteringTab(master, logger, sample_provider, *, on_message=None, on_result=None)` | `run()`, `read_parameters(method=None)`, `read_seed()`, `show_plot(title=None)`, `fill_tables()`, `toggle_legend()`, `refresh_legend()`, `refresh_sample_info()`, `on_tab_activated()`. Для интерактивного α: `get_engine(sample, metric, linkage)`, `set_alpha_value(value, *, recompute=True)`, `apply_alpha_change()`, `show_profile_plot()`, `show_matrix_plot(engine, result)`, `toggle_alpha_play()`, `start_alpha_play()`, `stop_alpha_play()`, `advance_alpha_play()`, `_sync_view_tabs()`; свойства `engine`, `profile`. Закладки «Профиль k(α)» и «Матрица сходства» активны только для метода α-уровня, у остальных методов отключены. Для пошаговой агломерации (метод «по порогу»): `get_trace(sample, metric)`, `step_agglomeration()`, `reset_agglomeration()`, `toggle_step_play()`, `start_step_play()`, `stop_step_play()`, `set_step_speed(speed, *, reschedule=True)`, `step_interval_ms()`; свойства `trace`, `step_index`, `step_speed_scale` |
| `LogTab(master, logger, *, on_message=None, autoupdate_ms=2000)` | `reload()`, `save_as()`, `save_to(path)`, `on_tab_activated()`, `autoupdate_active` |

Константы: `APP_TITLE`, `WINDOW_SIZE = (1180, 780)`, `TAB_TITLES`,
`TAB_DESCRIPTIONS`, `TAB_HINTS`.

**Точка входа**

```python
main(argv=None) -> int
```

Разбирает аргументы командной строки (`--log-dir`, `--help`), создаёт
`FuzzyApp` и запускает главный цикл. Возвращает `0` при обычном завершении и `2`,
если графическое окно открыть не удалось (например, на сервере без дисплея).

**Пример запуска собственного окна с библиотекой**

```python
import tkinter as tk
from gui.app import FuzzyApp, TAB_GENERATION

root = tk.Tk()
app = FuzzyApp(master=root, log_dir="logs")
tab = app.tabs[TAB_GENERATION]
tab.count_low.set("150")
tab.count_high.set("150")
tab.seed_entry.set("2026")
tab.generate()          # выборка создана без запуска mainloop
root.mainloop()
```

---

## 6. Соглашения и ограничения

- **Числа вместо величин.** Всюду, где ожидается величина, можно передать
  число: оно трактуется как вырожденная величина `[x, x]`.
- **Ошибки.** Предметные ошибки — подклассы `ValueError`
  (`FuzzyVariableError`, `FuzzySetError`); неподходящий тип аргумента —
  `TypeError`. Сообщения самодостаточны: в них указаны параметр, полученное
  значение и допустимый диапазон.
- **Направление зависимостей.** `gui` → `logger` → `fuzzy_core`; обратных
  зависимостей нет, поэтому ядро можно использовать без интерфейса и без
  журнала.
- **Детерминированность.** При заданном зерне выборка и результат K-Means
  воспроизводимы. Порядок кластеров всегда одинаков (сортировка по центроиду),
  поэтому индексы кластеров устойчивы между запусками. Метод «по порогу» и
  плотностной метод детерминированы полностью (зерно им не нужно).
- **Потокобезопасность.** Классы библиотеки не синхронизированы; интерфейс
  Tkinter должен работать в главном потоке. Для фоновых вычислений создавайте
  отдельный объект `SessionLogger` и передавайте результаты в окно через
  `set_status` и `remember_sample`.
- **Формат журнала.** Текстовый файл в UTF-8 с метками вида
  `ГГГГ-ММ-ДД ЧЧ:ММ:СС,мс | УРОВЕНЬ | сообщение`, пригоден для чтения любым
  текстовым редактором и для автоматического разбора.

---

## 7. Расширение библиотеки

| Что нужно | Как сделать |
| --- | --- |
| Своя метрика расстояния | добавить функцию в словарь `DISTANCE_METRICS`; далее её можно указывать по имени в `distance`, `cluster` и т. д. |
| Свой набор распределений генератора | передать свои `a_range`, `width_range`, `count_range` в `generate_sample` |
| Своя вкладка интерфейса | создать класс на основе `ttk.Frame` с методами `on_tab_activated()` (вызывается при переходе на вкладку) и зарегистрировать его в `FuzzyApp._build_tabs` |
| Другой вид функции принадлежности | новый класс должен предоставлять `a`, `b`, `center`, `width`, `membership(x)`, арифметические операторы, `distance` и `rank_key`: на эти члены опираются метрики, сравнение и кластеризация |
| Отчёт по результатам | использовать `ClusterResult.to_dict()` и `Cluster.to_dict()` — они возвращают только простые типы |
