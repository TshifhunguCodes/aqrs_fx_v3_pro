import csv
with open('backtest_results.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        print(f'{row["symbol"]:8s} {row["direction"]:5s} '
              f'entry={float(row["entry"]):.5f} '
              f'sl={float(row["sl"]):.5f} '
              f'tp={float(row["tp"]):.5f} '
              f'pnl={row["pnl"]:>8s} '
              f'rr={row["rr"]:s} '
              f'regime={row["regime"]:s} '
              f'lifecycle={row["lifecycle"]:s} '
              f'exit={row.get("exit_reason","?")}')