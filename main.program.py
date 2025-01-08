import requests as req
from bs4 import BeautifulSoup as soup
import time,csv,os

def data_update():
    urls = ["https://tw.stock.yahoo.com/quote/00881","https://tw.stock.yahoo.com/quote/2312.TW","https://tw.stock.yahoo.com/quote/2330","https://tw.stock.yahoo.com/quote/2344","https://tw.stock.yahoo.com/quote/2461.TW","https://tw.stock.yahoo.com/quote/3686.TW","https://tw.stock.yahoo.com/quote/6213"]
    file = open("C:\\Users\\user\\Desktop\\python-program\\data_base.csv","w",newline ="",encoding = "utf-8")
    for url in urls:
        data = req.get(url)
        page = soup(data.text,"html.parser")
        
        writer = csv.writer(file)
        write = []    
        stock_number = page.find("span",{"class":"C($c-icon) Fz(24px) Mend(20px)"}).text.strip()
        write.append(stock_number)
        stock_name = page.find("h1").text.strip()
        print(stock_number + stock_name)
        
        lis = page.find_all("li","price-detail-item H(32px) Mx(16px) D(f) Jc(sb) Ai(c) Bxz(bb) Px(0px) Py(4px) Bdbs(s) Bdbc($bd-primary-divider) Bdbw(1px)")
        for i in lis:
            spans = i.find_all("span")
            title = spans[0].text.strip()
            number = spans[1].text.strip()
            write.append(number)
            print(title,number)
        writer.writerow(write)
        print()
    file.close()
    print("=============================")

def KD_update():
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

def KD_analyze():
    stock_number_name = {"00881":"國泰台灣5G+","2312":"金寶","2330":"台積電","2461":"光群雷","2344":"華邦電","3686":"達能","6213":"聯茂"}
    KD_analyze = os.listdir("KD_analyze")
    for kd_analyze in KD_analyze:
        path = os.path.join('C:\\Users\\user\\Desktop\\python-program\\KD_analyze',kd_analyze)
        with open(path,"r",encoding="utf-8") as file:
            csvreader = csv.reader(file)
            rows = []
            for row in csvreader:
                rows.append(row)
        stock_name = stock_number_name.get(rows[0][0])
        print(rows[0][0],stock_name,end=" ")
        t_k = float(rows[2][8])
        y_k = float(rows[2][7])
        by_k = float(rows[2][6])
        t_d = float(rows[3][8])
        y_d = float(rows[3][7])
        if(t_k >= 80 and y_k >= 80 and by_k >= 80):
            print("高檔鈍化 K=",round(t_k,2),"D=",round(t_d,2),"*")
        elif(t_k <= 20 and y_k <= 20 and by_k <= 20):
            print("低檔鈍化 K=",round(t_k,2),"D=",round(t_d,2),"*")
        elif(y_k >= 80 and y_k > y_d and t_k < y_d):
            print("死亡交叉 K=",round(t_k,2),"D=",round(t_d,2),"*")
        elif(y_k <= 20 and y_k < y_d and t_k > y_d):
            print("黃金交叉 K=",round(t_k,2),"D=",round(t_d,2),"*")
        elif(t_k >= 80):
            print("K進入超買區 K=",round(t_k,2),"D=",round(t_d,2),"*")
        elif(t_k <= 20):
            print("K進入超賣區 K=",round(t_k,2),"D=",round(t_d,2),"*")
        else:
            print("None K=",round(t_k,2),"D=",round(t_d,2))


while True:
    current_time = time.localtime()
    while(current_time[3] >= 9 and current_time[3] < 14):
        data_update()
        time.sleep(600)
        current_time = time.localtime()
    if(current_time[3] >= 14):
        data_update()
        KD_update()
        print("KD分析")
        KD_analyze()
        print("=============================\n程式關閉")
        break
