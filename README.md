# Daily News Intelligence

Hệ thống tự động thu thập và tạo bản tin hằng ngày bằng **Tiếng Việt + English** về:

- Công nghệ thế giới và Việt Nam
- Repository GitHub mới nổi
- Thị trường tài chính
- Nhu cầu xã hội, việc làm, chuyển đổi số và năng lượng

Kết quả được xuất thành Markdown, JSON và một trang HTML dễ đọc. Pipeline có thể chạy thủ công hoặc tự động mỗi ngày bằng GitHub Actions.

## Chạy nhanh

Yêu cầu Python 3.11+; không cần cài package ngoài.

```powershell
python -m daily_news
```

Mở file mới nhất trong `output/`. Nếu có OpenAI API key, hệ thống sẽ tóm tắt và dịch tự nhiên hơn:

```powershell
$env:OPENAI_API_KEY="..."
python -m daily_news
```

Không có API key, pipeline tự dùng dịch máy công khai làm fallback. Để chạy backend API và dashboard theo ngày:

```powershell
python -m daily_news.server
```

Sau đó mở `http://localhost:8000`. Backend dùng SQLite tại `data/daily_news.db`.
Backend mặc định tự gọi pipeline mỗi 5 giờ. Tắt scheduler nội bộ khi đã có cron/GitHub Actions bên ngoài:

```powershell
python -m daily_news.server --refresh-hours 0
```

Khi backend khởi động, pipeline chạy một lượt ngay trong background rồi tiếp tục mỗi 5 giờ. Dùng `--no-refresh-on-start` nếu muốn chờ đến chu kỳ đầu tiên.

### Deploy bằng Docker

```powershell
docker compose up -d --build
```

Volume `signal-daily-data` giữ SQLite và archive khi chạy Docker trên máy cá nhân.

Trên Render Free, container chỉ đọc snapshot database được đóng gói từ repository. GitHub Actions chạy khoảng 5 giờ/lần, cập nhật SQLite/archive, commit lên `main`, và Render tự deploy snapshot mới. Cách này không cần thẻ hoặc persistent disk. Render Free có thể ngủ khi ít truy cập nên request đầu tiên sau thời gian nghỉ có thể chậm.

### Lưu trữ theo tháng

Mỗi lần pipeline chạy, các tháng đã kết thúc sẽ tự động được:

1. Gộp thành `data/archives/YYYY-MM.json.gz`.
2. Đọc lại và kiểm tra đủ ngày/số bản tin.
3. Chỉ sau khi xác minh thành công mới xóa dữ liệu tháng đó khỏi SQLite.

API vẫn đọc trực tiếp file lưu trữ nên các ngày cũ tiếp tục xuất hiện trên website. Chạy thủ công:

```powershell
python -m daily_news.archive
python -m daily_news.archive --month 2026-07
```

API:

- `GET /api/health`
- `GET /api/editions`
- `GET /api/editions/YYYY-MM-DD`
- `GET /api/archives`

Tùy chọn:

```powershell
python -m daily_news --config config.json --output output --date 2026-08-04
```

## Cấu hình

Chỉnh [config.json](config.json):

- `feeds`: nguồn RSS theo nhóm và thị trường.
- `github`: số ngày, ngôn ngữ và ngưỡng sao cho repo mới nổi.
- `finance.symbols`: mã theo Yahoo Finance (`^GSPC`, `GC=F`, `BTC-USD`, ...).
- `limits`: số tin tối đa mỗi nhóm.
- `openai`: model và kích thước batch. Có thể đổi bằng `OPENAI_MODEL`.

Nếu một nguồn lỗi, pipeline tiếp tục với các nguồn còn lại và ghi cảnh báo trong JSON. Nội dung được khử trùng lặp theo URL và tiêu đề.

## Tự động hằng ngày

Workflow `.github/workflows/daily-news.yml` chạy khoảng **5 giờ một lần** tại phút 15 (UTC: 00:15, 05:15, 10:15, 15:15 và 20:15), lưu artifact trong 30 ngày và commit bản tin mới về repository. Các lần chạy trong cùng ngày cập nhật bản ghi hiện có bằng UPSERT, không tạo ngày trùng lặp.

Để bật AI summary, thêm repository secret `OPENAI_API_KEY`. Workflow vẫn chạy được nếu không có secret.

AI không tham gia vào việc tải RSS/API, khử trùng lặp, chấm điểm, lưu SQLite hay archive tháng. Không có API key, hệ thống vẫn vận hành đầy đủ và dùng dịch máy miễn phí; OpenAI chỉ giúp phần tóm tắt và dịch tự nhiên hơn.

## Gemini Opportunity Analyst

Đặt `NVIDIA_API_KEY` ở backend để bật phân tích cơ hội SaaS và chatbot có dẫn nguồn qua NVIDIA OpenAI-compatible API. Mặc định dùng `AI_BASE_URL=https://integrate.api.nvidia.com/v1` và `AI_MODEL=z-ai/glm-5.2`. Gemini vẫn là fallback khi đặt `AI_PROVIDER=gemini`. Pipeline gọi AI một lần mỗi lượt để tạo tối đa 5 cơ hội; API `/api/chat` truy xuất các bài liên quan và giới hạn 10 câu hỏi/IP/giờ. Key không được đưa xuống frontend hoặc commit vào repository.

## Cấu trúc

```text
daily_news/       Collector, ranking, bilingual enrichment, renderer
config.json       Nguồn và tham số
output/           Bản tin sinh ra
tests/            Unit tests không gọi mạng
```

## Lưu ý nguồn và pháp lý

Hệ thống chỉ lưu tiêu đề, đoạn mô tả ngắn, metadata và link về bài gốc. Hãy tuân thủ điều khoản sử dụng của từng nguồn. Dữ liệu tài chính mang tính tham khảo, không phải lời khuyên đầu tư.
