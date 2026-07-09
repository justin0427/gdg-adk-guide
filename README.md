# GDG on Campus — Google ADK 課程講義

用 Google ADK ＋ 地端 LLM 打造你的第一支 AI Agent，一小時課程用的學員講義。

課程程式碼與環境設定請見 [gdg-adk-demo](https://github.com/justin0427/gdg-adk-demo)。這個 repo 只放講義本體，方便用 GitHub Pages 發布、掃 QR code 直接看。

## 更新講義

`STUDENT_GUIDE.md` 是內容來源，改完後執行：

```bash
python3 build_html.py STUDENT_GUIDE.md
cp STUDENT_GUIDE.html index.html
```

重新產生自包含的 `index.html`（GitHub Pages 首頁）。
