"""Z5 RESEARCH - klasyfikator bez LLM-a.

Pipeline:
  1. pobierz lab_data.zip (correct/incorrect/verify),
  2. zrób inżynierię cech (pary XOR + progi sumy) - reguła nie jest liniowa,
  3. wytrenuj małe drzewo decyzyjne (CART) i sprawdź F1 w walidacji krzyżowej,
  4. wytypuj ID z verify.txt i wyślij listę.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from tools import mini_ml


def parse_rows(text: str, sep: str = ",") -> dict[int, list[int]]:
    out = {}
    for line in text.strip().splitlines():
        if not line.strip():
            continue
        ident, _, rest = line.partition("=" if "=" in line else ",")
        bits = [int(v) for v in rest.replace(",", " ").split()]
        out[int(ident)] = bits
    return out


def main() -> None:
    lab = common.unzip(common.data("research", "lab_data.zip"))
    correct = parse_rows(lab["correct.txt"].decode())
    incorrect = parse_rows(lab["incorrect.txt"].decode())
    verify = parse_rows(lab["verify.txt"].decode())
    print(f"[*] correct={len(correct)} incorrect={len(incorrect)} verify={len(verify)}")

    X = [mini_ml.features(b) for b in list(correct.values()) + list(incorrect.values())]
    y = [1] * len(correct) + [0] * len(incorrect)
    # tasowanie: klasy nie mogą być skupione w jednym foldzie
    import random
    order = list(range(len(X)))
    random.Random(42).shuffle(order)
    X = [X[i] for i in order]
    y = [y[i] for i in order]

    # walidacja krzyżowa 3-fold
    f1s = []
    fold = len(X) // 3
    for k in range(3):
        idx_te = list(range(k * fold, (k + 1) * fold))
        te_set = set(idx_te)
        idx_tr = [i for i in range(len(X)) if i not in te_set]
        tree = mini_ml.TinyTree(max_depth=5).fit([X[i] for i in idx_tr], [y[i] for i in idx_tr])
        f1, prec, rec = mini_ml.f1_score([y[i] for i in idx_te],
                                         [tree.predict_one(X[i]) for i in idx_te])
        f1s.append(f1)
    print(f"[*] F1 w walidacji krzyżowej: {[round(f, 3) for f in f1s]}")

    tree = mini_ml.TinyTree(max_depth=5).fit(X, y)
    ids = [ident for ident, bits in sorted(verify.items()) if tree.predict_one(mini_ml.features(bits)) == 1]
    print(f"[*] wytypowane ID ({len(ids)}): {ids[:15]}...")
    common.report("research", ids)


if __name__ == "__main__":
    main()
