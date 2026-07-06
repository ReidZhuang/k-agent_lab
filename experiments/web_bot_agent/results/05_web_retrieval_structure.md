# 🧭 前端架构与后端交互分析报告

**URL:** https://www.stcn.com
**标题:** 证券时报官方网站-中国资本市场信息披露平台
**描述:** 证券时报，证券时报网，由人民日报社主管主办，是证券市场权威信息披露媒体，也是中国资本市场的重要信息披露平台。提供全天候7*24小时财经证券类资讯，内容丰富，包括时报快讯、股市新闻、财经资讯、基金净值、债券、期货、上市公司公告等，为用户提供全方位、最新鲜的财经信息。打造了

---

## 🏗️ 前端架构画像

- **框架候选:** 未明显检测到
- **SPA 判定:** ❌ 更像 MPA
- **CSS 框架:** Bootstrap, Ant Design, Element UI
- **Tailwind 迹象:** ✅

## 🔌 后端交互面（可通向后端的触点）

### 表单
- 表单 1: GET -> https://www.stcn.com/article/search.html
  - 字段: text(keyword)
- 表单 2: GET -> https://www.stcn.com/xinpi/report.html
  - 字段: text(stockshow)
- 表单 3: GET -> https://www.stcn.com/public/clarify.html
  - 字段: input(user_name), input(company_name), input(job), textarea(remark), file(file)
- 表单 4: GET -> https://www.stcn.com/public/proof.html
  - 字段: textarea(remark), input(source), file(file)

### API/HTTP 端点
- https://static-web.stcn.com/static/images/login-logo.png
- https://static-web.stcn.com/static/images/wx-login-logo.png
- https://static-web.stcn.com/static/images/qr.png
- https://v1.cnzz.com/z_stat.php%3Fid%3D1281191046
- https://v1.cnzz.com/z_stat.php%3Fid%3D1281265122
- https://s9.cnzz.com/z_stat.php%3Fid%3D1281169049
- https://s4.cnzz.com/z_stat.php%3Fid%3D1281264856

- **Cookie 使用:** ❌ 未发现
- **存储使用:** localStorage: ❌, sessionStorage: ❌
- **CSRF 线索:** meta: ✅, hidden: ❌

## 📦 资源清单（前20）

### Scripts
- https://static-web.stcn.com/static/v3/scripts/tailwindcss-3.4.17.min.js
- https://static-web.stcn.com/static/scripts/jquery.min.js
- https://static-web.stcn.com/static/scripts/jquery-migrate.min.js
- https://static-web.stcn.com/static/scripts/jsencrypt.min.js
- https://static-web.stcn.com/static/scripts/lodash.min.js?v=20260318
- https://static-web.stcn.com/static/scripts/layer/layer.js
- https://static-web.stcn.com/static/scripts/swiper/swiper-bundle.min.js
- https://static-web.stcn.com/static/scripts/echarts-index.min.js
- https://static-web.stcn.com/static/scripts/fancybox/fancybox.umd.js
- https://static-web.stcn.com/static/scripts/dayjs.min.js
- https://static-web.stcn.com/static/v3/scripts/common.js?v=20260623
- https://static-web.stcn.com/static/scripts/xinpi.js?v=20260331
- https://static-web.stcn.com/static/v3/scripts/index.js?v=20260616
- https://static-web.stcn.com/static/scripts/clarify.js?v=20260330
- https://o.alicdn.com/captcha-frontend/aliyunCaptcha/AliyunCaptcha.js

### Stylesheets
- https://static-web.stcn.com/static/v3/styles/common.min.css?v=2026061801
- https://static-web.stcn.com/static/v3/styles/index.min.css?v=20260616
- https://static-web.stcn.com/static/styles/chuangtou.css
- https://static-web.stcn.com/static/styles/clarify.css?v=20260330
- https://static-web.stcn.com/static/styles/login.css?v=20260330
- https://static-web.stcn.com/static/scripts/swiper/swiper-bundle.min.css
- https://static-web.stcn.com/static/scripts/fancybox/fancybox.css

### Images
- https://static-web.stcn.com/static/v3/images/rmrb-icon.png
- https://static-web.stcn.com/static/v3/images/slogan.png
- https://static-web.stcn.com/static/v3/images/search-icon.png (搜索)
- https://static-web.stcn.com/static/images/qr.png
- https://static-web.stcn.com/static/images/zqsb.png
- https://static-web.stcn.com/static/images/stcn.png
- https://static-web.stcn.com/upload/2026/0701/07/6a4453d39662df83c074.jpg?x-oss-process=image/resize,m_fill,w_676,h_380 (清华大学五道口金融学院院长焦捷：AI重塑金融运行生态)
- https://static-web.stcn.com/upload/2026/0626/11/6a3def130f1467b38e1f.png?x-oss-process=image/resize,m_fill,w_676,h_380 (做好“五篇大文章” 赋能新质生产力丨华宝证券)
- https://static-web.stcn.com/upload/2026/0701/10/6a4478458ae4dc58f043.png?x-oss-process=image/resize,m_fill,w_676,h_380 (时报图说丨A股上半年收官：12股涨超500%！半导体领涨)
- https://static-web.stcn.com/upload/2026/0630/07/6a42fff7b5b266b94387.jpg?x-oss-process=image/resize,m_fill,w_676,h_380 (专题丨“十五五”产业看台)

---

*分析完成时间: 2026/7/1 22:17:20*