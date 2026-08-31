"""Weighted-average holdings math used when applying buy trades."""


def apply_buy(qty, avg, buy_qty, buy_price):
    new_qty = qty + buy_qty
    new_avg = (qty * avg + buy_qty * buy_price) / new_qty
    return new_qty, new_avg


def apply_sell(qty, avg, sell_qty, sell_price, fee=0):
    pnl = (sell_price - avg) * sell_qty - fee
    return qty - sell_qty, pnl


def test_pension_ocr_buys_from_2026_08_31():
    # 442570 RISE TDF2050액티브 적격
    q, avg = apply_buy(259, 15936, 20, 17375)
    assert q == 279
    assert abs(avg - 16039.1541218638) < 1e-6

    # 360750 TIGER 미국S&P500
    q, avg = apply_buy(404, 22369, 29, 26160)
    assert q == 433
    assert abs(avg - 22622.900692840646) < 1e-6


def test_sell_realized_pnl():
    qty, pnl = apply_sell(100, 10000, 10, 12000, fee=0)
    assert qty == 90
    assert pnl == 20000
