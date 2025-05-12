from flask import Flask, render_template, request, redirect, url_for, session
import random
import time
from itertools import product

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_change_coin_count(change):
    denominations = [10000, 5000, 1000, 500, 100, 50, 10, 5, 1]
    count = 0
    for coin in denominations:
        use = change // coin
        if use > 0:
            count += use
            change -= coin * use
    return count

def calculate_optimal_payment_with_change(price, wallet):
    from itertools import product

    denominations = sorted(wallet.keys(), reverse=True)
    limits = [wallet[coin] for coin in denominations]

    best_combo = None
    best_total_cost = float('inf')

    for counts in product(*(range(limit + 1) for limit in limits)):
        total_payment = sum(coin * count for coin, count in zip(denominations, counts))
        if total_payment < price:
            continue  # 不足は除外

        payment_count = sum(counts)
        change = total_payment - price
        change_count = get_change_coin_count(change)
        total_cost = payment_count + change_count

        # ぴったり支払いは最優先
        if change == 0:
            if total_cost < best_total_cost:
                best_combo = dict(zip(denominations, counts))
                best_total_cost = total_cost

        # ぴったりじゃなくても最小なら更新
        elif best_combo is None or total_cost < best_total_cost:
            best_combo = dict(zip(denominations, counts))
            best_total_cost = total_cost

    return best_combo, best_total_cost

def get_wallet_by_mode(mode: str) -> dict:
    if mode == 'coins':
        return {500: 2, 100: 6, 50: 6, 10: 5, 5: 5, 1: 5}

    elif mode == 'random':
        coins = [10000, 5000, 1000, 500, 100, 50, 10, 5, 1]
        while True:
            wallet = {coin: random.randint(0, 4) for coin in coins}
            return wallet

    # balance または fallback
    return {
        10000: 1, 5000: 1, 1000: 2, 500: 2, 100: 2,
        50: 2, 10: 2, 5: 2, 1: 2
    }


@app.route('/', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    max_limit = 0

    if 'mode' not in session:
        return redirect(url_for('select_mode'))

    mode = session.get('mode', 'balance')

    wallet = get_wallet_by_mode(mode)
    max_limit = sum(k * v for k, v in wallet.items())

    if request.method == 'POST':
        min_price = int(request.form['min_price'])
        max_price = int(request.form['max_price'])

        if max_price > max_limit:
            error = f"※ {mode}モードでは上限金額は{max_limit}円までです。"

        if min_price <= 0 or max_price <= 0:
            error = "※ 金額は1円以上で入力してください。"
        elif min_price > max_price:
            error = "※ 下限金額は上限金額より小さくしてください。"
        elif error is None:
            price = random.randint(min_price, max_price)
            session['start_time'] = time.time()
            return redirect(url_for('payment', price=price))

    return render_template('form.html', error=error, mode=mode, max_limit=max_limit)


@app.route('/payment', methods=['GET', 'POST'])
def payment():
    price = int(request.args.get('price'))
    error = None
    change = None
    payment_amount = 0
    change_use = None
    breakdown = None
    elapsed_time = None
    optimal_payment = None
    best_total_cost = None
    optimal_payment_amount = None
    optimal_change = None
    score_total = 0
    score_detail = {}
    used_coins = {}
    mode = session.get('mode', 'balance')
    optimize = False
    wallet = get_wallet_by_mode(mode)
    display_wallet = {k: v for k, v in wallet.items() if v > 0}

    if request.method == 'POST':
        optimize = request.form.get('optimize') == 'on'
        for coin in wallet.keys():
            count = int(request.form.get(f"use_{coin}", 0))
            if count > wallet[coin]:
                error = f"{coin}円が所持数を超えています。"
                break
            if count > 0:
                used_coins[coin] = count
                payment_amount += coin * count

        if error is None:
            if payment_amount < price:
                error = "※ 支払金額が購入金額より少ないです。"
            else:
                change = payment_amount - price
                change_use = change
                denominations = [10000, 5000, 1000, 500, 100, 50, 10, 5, 1]
                breakdown = {}
                for denomination in denominations:
                    count = change_use // denomination
                    if count > 0:
                        breakdown[denomination] = count
                        change_use -= count * denomination
                if optimize:
                    optimal_payment, best_total_cost = calculate_optimal_payment_with_change(price, wallet)
                    if optimal_payment:
                        optimal_payment_amount = sum(coin * cnt for coin, cnt in optimal_payment.items())
                        optimal_change = optimal_payment_amount - price

            end_time = time.time()
            elapsed_time = round(end_time - session.get('start_time', end_time), 2)

            # 支払い誤差スコア（最大40点）
            if price > 0:
                error_rate = abs(payment_amount - price) / price
                score_detail["金額誤差スコア"] = max(0, round((1 - error_rate) * 40))
            else:
                score_detail["金額誤差スコア"] = 0

            # 支払い枚数スコア（最大30点）
            payment_count = sum(used_coins.values())
            score_detail["支払い枚数スコア"] = max(0, 30 - min(payment_count, 15) * 2)

            # お釣り枚数スコア（最大20点）
            change_count = get_change_coin_count(change) if change is not None else 0
            score_detail["お釣り枚数スコア"] = max(0, 20 - change_count * 2)

            # 時間スコア（最大10点）
            if elapsed_time is not None:
                if elapsed_time <= 5:
                    score_detail["支払い時間スコア"] = 10
                elif elapsed_time <= 10:
                    score_detail["支払い時間スコア"] = 5
                else:
                    score_detail["支払い時間スコア"] = 0
            else:
                score_detail["支払い時間スコア"] = 0

            # 総合スコア計算
            score_total = sum(score_detail.values())

    return render_template(
        'payment.html',
        price=price,
        change=change,
        payment_amount=payment_amount,
        error=error,
        breakdown=breakdown,
        wallet=display_wallet,
        elapsed_time=elapsed_time,
        optimal_payment=optimal_payment,
        best_total_cost=best_total_cost,
        optimal_payment_amount=optimal_payment_amount,
        optimal_change=optimal_change,
        score_total=score_total,
        score_detail=score_detail,
        used_coins=used_coins,
        debug_optimize=optimize
    )

@app.route('/mode', methods=['GET', 'POST'])
def select_mode():
    if request.method == 'POST':
        session['mode'] = request.form['mode']
        return redirect(url_for('index'))
    return render_template('mode.html')


if __name__ == '__main__':
    app.run(debug=False)