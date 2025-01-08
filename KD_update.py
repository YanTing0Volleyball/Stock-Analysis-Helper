import csv,os

with open("C:\\Users\\user\\Desktop\\python-program\\data_base.csv","r",encoding="utf-8") as file:
    csvreader = csv.reader(file)
    data_base = []
    for row in csvreader:
        temp = [row[0],row[1]]
        data_base.append(temp)
    data_base = dict(data_base)


KD_analyze = os.listdir("KD_analyze")
for kd_analyze in KD_analyze:
    path = os.path.join('C:\\Users\\user\\Desktop\\python-program\\KD_analyze',kd_analyze)
    with open(path,"r",encoding="utf-8") as file:
        csvreader = csv.reader(file)
        rows = []
        for row in csvreader:
            rows.append(row)
    stock_number = rows[0][0]
    t_closing_price = data_base.get(stock_number)
    closing_prices = list(map(float,rows[1]))
    closing_prices.pop(0)
    closing_prices.append(float(t_closing_price))
    y_k = float(rows[2][8])
    y_d = float(rows[3][8])
    closing_prices.sort()
    RSV = (float(t_closing_price) - closing_prices[0])/(closing_prices[8]-closing_prices[0])*100
    t_k = y_k*(2/3) + RSV*(1/3)
    t_d = y_d*(2/3) + t_k*(1/3)
    rows[1].pop(0)
    rows[1].append(t_closing_price)
    rows[2].pop(0)
    rows[2].append(str(t_k))
    rows[3].pop(0)
    rows[3].append(str(t_d))
    with open(path,"w",newline="",encoding="utf-8") as file:
        csvwriter = csv.writer(file)
        for row in rows:
            csvwriter.writerow(row)
    



