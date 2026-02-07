import time
#导入自动化模块
from DrissionPage import ChromiumPage
#打开浏览器
dp=ChromiumPage()
#打开京东商品页面
dp.get("https://item.jd.com/100209268189.html?spmTag=YTAyMTkuYjAwMjM1Ni5jMDAwMDQ2ODkuMCUyM2hpc2tleXdvcmQlMkNhMDI0MC5iMDAyNDkzLmMwMDAwNDAyNy4xJTIzc2t1X2NhcmQ")
time.sleep(2)
#监听数据
dp.listen.start('client.action')
#定位全部评价
dp.ele('text=全部评价').click()
#等待数据包加载
resp=dp.listen.wait(2)
#获取响应的数据内容
json_data=resp[-1].response.body
print(json_data)
