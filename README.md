# Hướng Dẫn Chạy Dự Án: Gemma 4 Q&A Chat App & Font Metadata Indexer

Dự án này gồm hai thành phần chính:
1. **Gemma 4 Q&A Chatbot**: Ứng dụng web chat giao tiếp với mô hình LLM thông qua API tùy biến (Uvicorn FastAPI).
2. **Font Metadata Indexer**: Module quét phông chữ hệ thống, phân tích sâu các thông số kỹ thuật nâng cao và lập chỉ mục vào Elasticsearch (hỗ trợ HTTP và xác thực).

---

## 1. Yêu cầu hệ thống & Cài đặt

Dự án chạy trên môi trường Windows và sử dụng trình khởi chạy Python `py`.

### Bước 1: Cài đặt dependencies
Chạy lệnh sau để cài đặt các thư viện cần thiết:
```powershell
py -m pip install -r requirements.txt
```
*Lưu ý: Thư viện `elasticsearch` đã được cấu hình cố định ở phiên bản `8.x` để đảm bảo tương thích tốt nhất với Elasticsearch Server.*

### Bước 2: Thiết lập cấu hình tệp môi trường
Tạo hoặc mở tệp `.env` tại thư mục gốc của dự án và điền các thông số kết nối:
```env
# 1. Cấu hình cho Chatbot LLM
LLM_API_BASE=http://171.232.252.198:4000/v1
LLM_API_KEY=sk-CIt4BMacaFUinEoL4unv-w
LLM_MODEL=google/gemma-4-31b-it

# 2. Cấu hình cho FastAPI App
HOST=127.0.0.1
PORT=8000

# 3. Cấu hình cho Elasticsearch (Chỉ dùng HTTP thuần + Tài khoản đăng nhập)
ELASTICSEARCH_URL=http://171.232.252.198:9200
ELASTICSEARCH_USER=elastic
ELASTICSEARCH_PASSWORD=elastic
```

---

## 2. Hướng dẫn chạy Gemma Q&A Chat App

Ứng dụng chatbot cung cấp giao diện web thân thiện để trao đổi thông tin với mô hình LLM.

### Khởi chạy server:
```powershell
py main.py
```

### Trải nghiệm giao diện:
- Sau khi khởi động thành công, hãy truy cập vào địa chỉ: [http://localhost:8000/](http://localhost:8000/)
- Giao diện chat sử dụng hiệu ứng Glassmorphism hiện đại sẽ hiển thị để bạn bắt đầu hội thoại.

---

## 3. Hướng dẫn sử dụng Font Metadata Indexer

Công cụ quét toàn bộ metadata chuyên sâu của phông chữ (TrueType, OpenType, WOFF...) từ thư mục máy tính và lưu trữ có cấu trúc lên Elasticsearch index `metadata`.

Các trường thông tin được phân tích bao gồm:
*   **Thông tin phông chữ**: Family, Subfamily, Full Name, Designer, License, Copyright...
*   **Chỉ số đo đạc**: Units per EM, Bounding Box, Weight Class, Width Class, Ascents, Cap Heights, Italic angle, Monospaced flag...
*   **Trục biến thể (Variable Font Axes)**: wght, wdth, ital... (nếu là font động).
*   **Các tính năng Layout**: kern, liga, smcp, frac...
*   **Hỗ trợ tiếng Việt (`supports_vietnamese`)**: Tự động phân tích bảng mã ký tự (`cmap`) để nhận diện font có gõ được tiếng Việt hay không.

### Các lệnh điều khiển qua CLI (`index_fonts.py`):

#### 1. Kiểm tra kết nối tới Elasticsearch:
```powershell
py index_fonts.py ping
```
*Kết quả mong đợi: `Connection SUCCESS! Successfully authenticated and connected to Elasticsearch.`*

#### 2. Lập chỉ mục (Index) thư mục Font:
Duyệt qua một thư mục và đưa toàn bộ thông tin phông chữ lên Elasticsearch:
```powershell
py index_fonts.py index "C:\Windows\Fonts"
```
*Bạn có thể đổi tên index lưu trữ bằng cách thêm tham số `--index-name <tên>`.*

#### 3. Tìm kiếm phông chữ đã lập chỉ mục:
Tìm kiếm font dựa trên tên họ, nhà sản xuất, tác giả thiết kế hoặc các từ khóa mô tả:
```powershell
py index_fonts.py search "Arial"
```
Hoặc tìm kiếm phông chữ đậm (`bold`) giới hạn 5 kết quả hiển thị:
```powershell
py index_fonts.py search "bold" --size 5
```
