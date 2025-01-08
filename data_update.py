import requests as req
from bs4 import BeautifulSoup as soup
import csv

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