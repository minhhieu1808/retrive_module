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

---

## 4. Hướng Dẫn Sử Dụng API Tìm Kiếm Hình Ảnh (Postman & Integrations)

Module Tìm kiếm hình ảnh cung cấp các API RESTful giúp lập chỉ mục và thực hiện các truy vấn tìm kiếm ảnh tương tự bằng văn bản (Text-to-Image) hoặc hình ảnh (Image-to-Image). Dưới đây là mô tả chi tiết cách cấu hình và gọi các API này bằng **Postman**.

### 4.1. Lập chỉ mục thư mục ảnh (Index Images)
API này quét toàn bộ các tệp hình ảnh nằm trong thư mục `image` tại thư mục gốc dự án, tự động thay đổi kích thước (resize) về tối đa 512px để tối ưu dung lượng payload và tránh tràn RAM GPU, tạo vector embedding, đồng thời gọi mô hình Vision LLM (`google/gemma-4-31b-it`) để tự động tạo mô tả ảnh bằng tiếng Việt và lưu tất cả vào Elasticsearch.

*   **URL**: `http://127.0.0.1:8000/api/images/index`
*   **Method**: `POST`
*   **Headers**:
    *   `Content-Type`: `application/json`
*   **Request Body (Body)**: Chọn `none` (Trống)
*   **Cách thiết lập trong Postman**:
    1.  Tạo request mới, chọn phương thức là `POST`.
    2.  Nhập URL: `http://127.0.0.1:8000/api/images/index`.
    3.  Nhấn **Send**.
*   **Response mẫu (200 OK)**:
    ```json
    {
      "total_processed": 3,
      "success_count": 3,
      "fail_count": 0,
      "errors": {}
    }
    ```

---

### 4.2. Tìm kiếm hình ảnh bằng mô tả văn bản (Text-to-Image Search)
Tìm kiếm các hình ảnh trong hệ thống dựa trên mô tả văn bản tiếng Việt/tiếng Anh.

*   **URL**: `http://127.0.0.1:8000/api/images/search`
*   **Method**: `GET`
*   **Headers**: *Trống*
*   **Query Parameters (Params)**:
    *   `query` (Bắt buộc): Chuỗi văn bản mô tả nội dung ảnh cần tìm (Ví dụ: `bục tròn màu nâu`, `bục gỗ màu trắng`).
    *   `limit` (Tùy chọn, mặc định: 6): Số lượng kết quả tối đa muốn nhận về.
*   **Cách thiết lập trong Postman**:
    1.  Tạo request mới, chọn phương thức là `GET`.
    2.  Nhập URL: `http://127.0.0.1:8000/api/images/search`.
    3.  Tại tab **Params**, nhập các cặp key-value:
        *   `query`: `bục tròn màu nâu`
        *   `limit`: `2`
    4.  Nhấn **Send**.
*   **Response mẫu (200 OK)**:
    ```json
    {
      "results": [
        {
          "id": "1f26399e-08f2-429b-8ea7-5023b27ec899",
          "score": 0.3594,
          "percentage": 67.97,
          "file_name": "1f26399e-08f2-429b-8ea7-5023b27ec899.jpg",
          "file_path": "D:\\retrive\\image\\1f26399e-08f2-429b-8ea7-5023b27ec899.jpg",
          "timestamp": "2026-06-04T16:05:12.123456+00:00",
          "description": "Hình ảnh là một bục trưng bày hình tròn, màu nâu nhạt/be, đặt trên nền tối giản cùng tông màu trung tính. Phong cách thiết kế 3D hiện đại, sạch sẽ, tạo cảm giác nhẹ nhàng và sang trọng."
        }
      ]
    }
    ```

---

### 4.3. Tìm kiếm hình ảnh bằng cách tải ảnh lên trực tiếp (Image-to-Image Search - Multipart)
Tìm kiếm các hình ảnh tương đồng bằng cách upload trực tiếp một file ảnh từ máy tính của bạn (đây là cách nhanh nhất và thuận tiện nhất khi dùng Postman).

*   **URL**: `http://127.0.0.1:8000/api/images/search-by-image-file`
*   **Method**: `POST`
*   **Headers**: *Trống* (Postman sẽ tự động sinh header `multipart/form-data` kèm boundary khi bạn tải file).
*   **Request Body (Body)**: Chọn kiểu **form-data**
    *   `file` (Kiểu: **File**, Bắt buộc): Chọn tệp hình ảnh từ máy tính của bạn.
    *   `limit` (Kiểu: **Text**, Tùy chọn, mặc định: 6): Số lượng kết quả tối đa muốn nhận về.
*   **Cách thiết lập trong Postman**:
    1.  Tạo request mới, chọn phương thức là `POST`.
    2.  Nhập URL: `http://127.0.0.1:8000/api/images/search-by-image-file`.
    3.  Vào tab **Body**, chọn **form-data**.
    4.  Ở dòng đầu tiên: nhập key là `file`. Rê chuột vào phần cuối ô key để đổi kiểu dữ liệu từ **Text** sang **File**. Nhấn **Select Files** và tải ảnh lên.
    5.  Ở dòng thứ hai: nhập key là `limit` (kiểu Text), nhập value là `2`.
    6.  Nhấn **Send**.
*   **Response mẫu (200 OK)**:
    ```json
    {
      "results": [
        {
          "id": "1f26399e-08f2-429b-8ea7-5023b27ec899",
          "score": 1.0,
          "percentage": 100.0,
          "file_name": "91.jpg",
          "file_path": "D:\\retrive\\image\\91.jpg",
          "timestamp": "2026-06-04T16:05:15.123456+00:00",
          "description": "Bộ sưu tập các bục trưng bày sản phẩm 3D với nhiều hình dáng khác nhau như hình trụ tròn và hình khối chữ nhật. Tất cả đều có màu trắng tinh khôi, phong cách tối giản, hiện đại trên nền trắng."
        }
      ]
    }
    ```

---

### 4.4. Tìm kiếm hình ảnh bằng chuỗi Base64 (Image-to-Image Search - Base64 JSON)
Tìm kiếm các hình ảnh tương đồng bằng cách gửi chuỗi Base64 của ảnh trong JSON payload.

*   **URL**: `http://127.0.0.1:8000/api/images/search-by-image`
*   **Method**: `POST`
*   **Headers**:
    *   `Content-Type`: `application/json`
*   **Request Body (Body)**: Chọn **raw**, định dạng **JSON**
    *   `image` (string, Bắt buộc): Chuỗi Base64 Data URL của ảnh (Ví dụ: `data:image/jpeg;base64,...` hoặc chuỗi base64 thuần).
    *   `limit` (integer, Tùy chọn, mặc định: 6): Số lượng kết quả tối đa.
*   **Cách thiết lập trong Postman**:
    1.  Tạo request mới, chọn phương thức là `POST`.
    2.  Nhập URL: `http://127.0.0.1:8000/api/images/search-by-image`.
    3.  Vào tab **Body**, chọn **raw**, đổi kiểu từ `Text` sang `JSON`.
    4.  Nhập JSON body:
        ```json
        {
          "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP...",
          "limit": 2
        }
        ```
    5.  Nhấn **Send**.

