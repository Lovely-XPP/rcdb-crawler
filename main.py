from rcdb_crawler import Crawler

if __name__ == "__main__":
    # 输入跳过的webid
    skip_webid = []
    for i in range(18146, 18155+1):
        skip_webid.append(i)

    rcdb = Crawler(filename='data.xlsx', thread=32, skip_webid=skip_webid, fig=True)

    # 开始运行
    rcdb.main()

    
