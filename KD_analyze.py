import csv,os


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

