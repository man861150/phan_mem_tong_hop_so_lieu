# Hướng dẫn sử dụng website Tổng hợp số liệu

**Dành cho: Cán bộ nhập liệu**

Website: **Tổng hợp số liệu — Trung tâm Khởi nghiệp sáng tạo Thành phố Hồ Chí Minh**

---

## 1. Vai trò của Cán bộ nhập liệu

Tài khoản Cán bộ nhập liệu được gắn với **một phòng ban**. Bạn chỉ nhìn thấy và nhập liệu cho phòng ban của mình.

Bạn có thể:

- Nhập, sửa, lưu nháp và gửi duyệt phiếu kết quả hoạt động.
- Nhập phiếu tháng và phiếu hỗ trợ dự án.
- Xem tiến độ thực hiện chỉ tiêu của phòng.
- Lập và xuất báo cáo tổng hợp của phòng.
- Tra cứu lịch sử, xem lịch sử thay đổi số liệu.

Bạn **không** có quyền:

- Duyệt, trả lại hoặc mở lại phiếu (do Lãnh đạo phòng thực hiện).
- Quản lý người dùng, danh mục, kỳ báo cáo (do Quản trị hệ thống thực hiện).

> Sau khi gửi duyệt, phiếu sẽ bị khóa. Muốn sửa tiếp, phiếu phải được Lãnh đạo phòng **trả lại**.

---

## 2. Đăng nhập và đăng xuất

### Đăng nhập

1. Mở địa chỉ website do đơn vị cung cấp.
2. Chọn **Đăng nhập** (hoặc truy cập `/dang-nhap/`).
3. Nhập **Tên đăng nhập** và **Mật khẩu** được cấp.
4. Bấm **Đăng nhập**.

Sau khi đăng nhập, hệ thống đưa bạn về **Trang chủ**.

### Đăng xuất

Ở góc phải thanh menu, bấm **Đăng xuất**.

> Nếu quên mật khẩu hoặc tài khoản bị khóa, liên hệ Quản trị hệ thống. Không dùng chung tài khoản với người khác.

---

## 3. Giao diện và menu

Thanh menu trên cùng hiển thị các mục bạn được phép dùng:

| Menu | Chức năng |
|---|---|
| **Trang chủ** | Tổng quan số liệu, phiếu nháp, phiếu bị trả lại |
| **Hoạt động** | Danh sách hoạt động, thêm hoạt động, nhập phiếu kết quả |
| **Dự án** | Danh sách dự án, thêm dự án, nhập hỗ trợ dự án |
| **Tiến độ** | Bảng tiến độ thực hiện chỉ tiêu |
| **Báo cáo** | Xem trước, đánh giá và xuất báo cáo |
| **Lịch sử** | Tra cứu, so sánh số liệu và lịch sử thay đổi |

Góc phải hiển thị **Họ tên — Vai trò** và nút **Đăng xuất**.

---

## 4. Trang chủ

Trang chủ gồm các khu vực:

- **Phiếu nháp của tôi**: các phiếu đang ở trạng thái Nháp. Bấm vào tên phiếu để mở.
- **Phiếu bị trả lại**: các phiếu bị Lãnh đạo phòng trả lại kèm ý kiến. Cần mở ra, sửa và gửi duyệt lại.
- **Thẻ % hoàn thành**: bình quân mức hoàn thành năm của phòng.
- **Biểu đồ**:
  - Bình quân % hoàn thành theo mảng chỉ tiêu.
  - Lũy kế so với kế hoạch năm.
- Nút **Xem bảng tiến độ** để mở trang Tiến độ.

> Chỉ tiêu “chỉ theo dõi” không được tính vào bình quân % hoàn thành.

---

## 5. Quy trình nhập liệu tổng quát

Một phiếu nhập liệu đi theo luồng:

```
Nháp → Gửi duyệt → Chờ duyệt → Duyệt → Đã duyệt
                                  │
                                  └→ Trả lại → (sửa) → Gửi duyệt lại

Đã duyệt → Mở lại → Nháp
```

| Trạng thái | Ý nghĩa | Bạn được làm gì? |
|---|---|---|
| **Nháp** | Chưa gửi | Sửa, lưu nháp, gửi duyệt, xóa nháp |
| **Chờ duyệt** | Đã gửi, chờ Lãnh đạo phòng | Chỉ xem |
| **Trả lại** | Bị trả lại kèm ý kiến | Sửa theo ý kiến, gửi duyệt lại |
| **Đã duyệt** | Đã được duyệt, số liệu chính thức | Chỉ xem |

**Lưu ý quan trọng:**

- **Lưu nháp** chưa kiểm tra các chỉ tiêu bắt buộc; có thể lưu khi còn thiếu.
- **Gửi duyệt** kiểm tra đầy đủ chỉ tiêu bắt buộc, quy tắc tổng/phân loại và sẽ khóa phiếu.
- Phiếu đã gửi hoặc đã duyệt **không sửa, không xóa** được.

---

## 6. Nhập phiếu kết quả hoạt động

### 6.1. Tạo hoạt động

1. Vào menu **Hoạt động**.
2. Bấm **Thêm hoạt động**.
3. Nhập các thông tin:
   - **Loại hoạt động** (quyết định phòng ban và bộ chỉ tiêu).
   - **Tên hoạt động**.
   - **Từ ngày**, **Đến ngày** (nếu để trống Đến ngày, hệ thống dùng ngày bắt đầu).
   - **Địa điểm**, **Hình thức**, **Lĩnh vực**, **Đối tượng hướng tới**.
   - **Đơn vị phối hợp**: tích chọn đơn vị có sẵn, hoặc nhập tên đơn vị mới rồi bấm **Thêm đơn vị**.
4. Bấm **Lưu hoạt động**.

> Với loại **Nhiệm vụ phát sinh**, form hiện thêm ô **Nội dung** và **Kết quả**. Hai ô này bắt buộc trước khi chuyển hoạt động sang Đã tổ chức, và không tạo ra số liệu định lượng.

### 6.2. Chuyển sang “Đã tổ chức”

1. Mở hoạt động từ danh sách.
2. Ở cuối trang, bấm **Chuyển sang Đã tổ chức**.
3. Nếu thiếu dữ liệu bắt buộc, hệ thống báo lỗi và giữ nguyên trạng thái Kế hoạch.

> **Chỉ hoạt động ở trạng thái “Đã tổ chức” mới được nhập phiếu kết quả.**

### 6.3. Mở phiếu kết quả

1. Trong trang chi tiết hoạt động đã tổ chức, bấm **Nhập phiếu kết quả**.
2. Hoặc vào menu **Hoạt động** → mở hoạt động → nút nhập phiếu.

Hệ thống tự tạo phiếu chính nếu chưa có.

### 6.4. Nhập số liệu

Mỗi chỉ tiêu là một thẻ, gồm:

- **Tên chỉ tiêu**, **đơn vị tính**, mã chỉ tiêu.
- Nhãn **Bắt buộc** nếu phải nhập khi gửi duyệt.
- Ô **Giá trị**.
- Ô **Nguồn số liệu** (chỉ hiện các nguồn được phép cho chỉ tiêu đó).
- Khu vực **Phân loại** nếu chỉ tiêu yêu cầu.

Quy tắc nhập số:

- Chỉ nhập **số không âm**.
- Tối đa **4 chữ số thập phân**.
- Dùng **dấu chấm** cho phần thập phân (ví dụ `12.5`), không nhập dấu phân cách nghìn.
- Nếu chọn **Nguồn số liệu** thì phải nhập **Giá trị**.
- Không nhập các chỉ tiêu **tự động tính** (tỷ lệ, đếm, lũy kế) — hệ thống tự tính.

### 6.5. Phân loại đối tượng

Nếu chỉ tiêu có **Phân loại đối tượng**:

- Nhập **Giá trị tổng** ở ô phía trên.
- Nhập giá trị cho từng đối tượng ở các dòng bên dưới.
- **Tổng các dòng đối tượng phải bằng đúng giá trị tổng.**
- Dòng “Tổng đang nhập” giúp bạn kiểm tra trước khi lưu.

Ví dụ: Tổng = 30; đối tượng A = 10, B = 20 → hợp lệ. Nếu A = 10, B = 10 → hệ thống báo lệch 10.

### 6.6. Phân loại lĩnh vực

Nếu chỉ tiêu có **Phân loại lĩnh vực**:

- Chọn lĩnh vực theo **QĐ 36** hoặc **TT 24**.
- Bấm **Thêm dòng QĐ 36** / **Thêm dòng TT 24** để thêm dòng.
- Bấm **Xóa** để bỏ dòng.
- Với mỗi hệ thống lĩnh vực được dùng, **tổng các dòng của hệ thống đó phải bằng giá trị tổng**.
- Không chọn trùng một lĩnh vực trong cùng một chỉ tiêu.

> Nếu chỉ tiêu chỉ dùng một hệ thống, hãy chỉ nhập cho hệ thống đó. Hệ thống kiểm tra tổng riêng của từng hệ thống (QĐ 36 và TT 24).

### 6.7. Lưu nháp và gửi duyệt

Cuối trang:

- **Lưu nháp**: lưu lại để làm tiếp; chưa bắt buộc nhập đủ chỉ tiêu.
- **Gửi duyệt**: kiểm tra và chuyển phiếu sang **Chờ duyệt**.

Khi gửi duyệt, nếu có lỗi, hệ thống hiển thị thông báo ngay trên form. Sửa hết lỗi rồi gửi lại.

### 6.8. Phiếu bổ sung

Với hoạt động đã tổ chức, có thể có nhiều phiếu:

- **Phiếu chính**: số liệu ban đầu.
- **Phiếu bổ sung**: số liệu khảo sát, hợp đồng hoặc bổ sung sau.

Bấm **Tạo phiếu bổ sung** trong trang phiếu. Phiếu bổ sung có trạng thái riêng, không làm thay đổi phiếu chính. Khi tạo phiếu bổ sung, nguồn số liệu mặc định là **“Phiếu khảo sát sau sự kiện”** nếu nguồn này có trong danh mục.

### 6.9. Xóa nháp

- Chỉ xóa được phiếu **Nháp** hoặc **Trả lại**.
- Bấm **Xóa nháp** và xác nhận.
- Toàn bộ số liệu của phiếu cũng bị xóa và **không khôi phục được**.

---

## 7. Nhập phiếu tháng

Phiếu tháng dùng cho các chỉ tiêu ghi nhận **theo tháng** của phòng.

### 7.1. Mở phiếu tháng

Màn hình phiếu tháng mở theo kỳ báo cáo:

```
/phieu/thang/<mã kỳ>/
```

> Hiện phiếu tháng chưa có mục riêng trên thanh menu. Hãy dùng đường dẫn do Quản trị hệ thống hoặc Lãnh đạo phòng cung cấp, hoặc mở từ liên kết kỳ báo cáo nếu có.

### 7.2. Nhập và theo dõi

- Kiểm tra **Kỳ đang mở** hay **Kỳ đã đóng** ở góc phải.
- **Kỳ đã đóng**: chỉ xem, không lưu.
- Mỗi chỉ tiêu hiển thị:
  - **Giá trị** kỳ này.
  - **Nguồn số liệu**.
  - **Tháng trước**.
  - **Lũy kế năm**.
- Nhập tương tự phiếu hoạt động: giá trị, nguồn, phân loại đối tượng/lĩnh vực.
- Bấm **Lưu nháp** hoặc **Gửi duyệt**.

Phần **Chỉ tiêu tự động tính** ở cuối trang hiển thị các chỉ tiêu tỷ lệ/đếm do hệ thống tính; bạn không nhập tay.

---

## 8. Nhập hỗ trợ dự án

### 8.1. Mở phiếu dự án

Màn hình hỗ trợ dự án mở theo dự án:

```
/phieu/du-an/<mã dự án>/
```

> Hiện phiếu dự án chưa có mục riêng trên thanh menu. Hãy mở từ đường dẫn được cung cấp hoặc từ màn hình dự án nếu có liên kết.

### 8.2. Thêm dòng hỗ trợ

Trong mục **Thêm dòng hỗ trợ**, nhập:

- **Loại hỗ trợ**: Ngày công lao động / Chuyên gia / Dịch vụ ươm tạo / Khác.
- **Ngày hỗ trợ**.
- **Số chuyên gia** (nếu có, không âm).
- **Nội dung**.

Bấm **Thêm dòng hỗ trợ**. Mỗi lần thêm một dòng; dòng đã thêm hiển thị trong bảng phía trên.

Sau khi nhập đủ, bấm **Gửi duyệt**.

> Phiếu dự án phải có ít nhất một dòng hỗ trợ mới được gửi duyệt.

---

## 9. Xem chi tiết và theo dõi phiếu

Trang **Phiếu nhập liệu #...** hiển thị:

- **Thông tin phiếu**: phòng ban, người nhập, ngày gửi, đối tượng.
- **Trạng thái** hiện tại.
- **Ý kiến trả lại gần nhất** (nếu bị trả lại).
- **Số liệu**: giá trị, phân loại, nguồn, so sánh kỳ trước, số liệu chính thức kỳ này.
- **Thay đổi từ lần gửi trước**: giúp Lãnh đạo phòng thấy bạn đã sửa gì.
- **Lịch sử xử lý**: ai gửi, duyệt, trả lại, mở lại và ý kiến kèm theo.

Các nút có thể gặp:

| Nút | Khi nào hiện | Ý nghĩa |
|---|---|---|
| **Gửi duyệt** | Phiếu Nháp/Trả lại | Chuyển sang Chờ duyệt |
| **Duyệt** | Chỉ Lãnh đạo phòng | Phê duyệt phiếu |
| **Trả lại** | Chỉ Lãnh đạo phòng | Trả phiếu kèm ý kiến bắt buộc |
| **Mở lại** | Chỉ Lãnh đạo phòng | Mở phiếu đã duyệt để sửa, phải nhập lý do |
| **Lịch sử thay đổi** | Có quyền xem lịch sử | Xem chi tiết từng lần sửa số liệu |

---

## 10. Xử lý khi phiếu bị trả lại

1. Vào **Trang chủ** → mục **Phiếu bị trả lại**, hoặc mở từ thông báo/chi tiết phiếu.
2. Đọc kỹ **Ý kiến trả lại** ở đầu trang.
3. Bấm vào hoạt động/phiếu để sửa số liệu.
4. Sửa theo đúng ý kiến.
5. Bấm **Gửi duyệt** lại.
6. Có thể xem mục **Thay đổi từ lần gửi trước** để tự kiểm tra.

> Không tạo phiếu mới để thay thế phiếu bị trả lại, trừ khi được Lãnh đạo phòng hướng dẫn.

---

## 11. Xem tiến độ

Vào menu **Tiến độ**.

- Chọn **Năm**.
- Phòng ban của bạn được cố định theo tài khoản.
- Bật **Gồm số chờ duyệt** nếu muốn xem cả số liệu chưa được duyệt.
- Bảng hiển thị theo phòng, theo mảng chỉ tiêu:
  - Kế hoạch năm.
  - Lũy kế.
  - % hoàn thành.
  - Còn lại.
  - Cờ **Chậm tiến độ** và **Chỉ theo dõi** (nếu có).
- Bấm tên chỉ tiêu để xem **chi tiết đóng góp** theo hoạt động/dự án.

> Cột “Lũy kế” chính thức chỉ tính phiếu **Đã duyệt**. Số **Chờ duyệt** chỉ hiển thị khi bật tùy chọn.

---

## 12. Lập và xuất báo cáo

Vào menu **Báo cáo**.

1. Chọn **Kỳ báo cáo**: Tháng hoặc Quý.
2. Chọn **Năm**, **Tháng/Quý**.
3. Phạm vi là phòng ban của bạn.
4. Bấm **Xem** để xem trước.
5. Nếu có **Số liệu chưa đầy đủ**, hệ thống liệt kê các chỉ tiêu còn thiếu. Có thể:
   - Quay lại nhập bổ sung, hoặc
   - Bấm **Vẫn lập báo cáo** để tiếp tục (báo cáo sẽ ghi chú số liệu chưa đầy đủ).
6. Nhập **Đánh giá hiệu quả** cho các chỉ tiêu cần đánh giá.
7. Bấm **Lưu đánh giá**.
8. Xuất báo cáo:
   - **Xuất Excel** (.xlsx)
   - **Xuất Word** (.docx)

Các nút phụ:

- **Báo cáo đã xuất**: danh sách báo cáo đã tạo, có thể tải lại.
- **Đọc file Excel**: tải file .xlsx do hệ thống xuất để xem trước cấu trúc. Chức năng này chỉ đọc và hiển thị, không ghi đè số liệu.

> Báo cáo đã xuất được lưu lại và không tự động thay đổi khi số liệu nguồn thay đổi.

---

## 13. Tra cứu và so sánh

Vào menu **Lịch sử**.

### Tra cứu

Lọc theo:

- Năm.
- Kỳ (cả năm, tháng, quý).
- Phòng ban (trong phạm vi được xem).
- Loại hoạt động.
- Lĩnh vực.
- Tên hoạt động/dự án/chỉ tiêu.
- Đơn vị phối hợp.

Kết quả gồm hai bảng:

- **Hoạt động**.
- **Phiếu nhập liệu và số liệu**, kèm liên kết **Chi tiết** và **Lịch sử xử lý**.

### So sánh cùng kỳ

Chọn:

- Kỳ: tháng hoặc quý.
- Năm A và Năm B.
- Phòng ban.

Hệ thống hiển thị giá trị kỳ A, kỳ B và chênh lệch.

---

## 14. Lỗi thường gặp và cách xử lý

| Thông báo / tình huống | Nguyên nhân | Cách xử lý |
|---|---|---|
| “Hoạt động chưa được tổ chức…” | Hoạt động còn ở trạng thái Kế hoạch | Chuyển hoạt động sang **Đã tổ chức** trước khi nhập phiếu |
| “Phiếu đang ở trạng thái … nên chỉ được xem” | Phiếu đã gửi/đã duyệt | Không sửa trực tiếp; đề nghị Lãnh đạo phòng trả lại/mở lại |
| “Chỉ tiêu này là bắt buộc khi gửi duyệt” | Thiếu chỉ tiêu bắt buộc | Nhập đủ rồi gửi lại, hoặc **Lưu nháp** |
| “Tổng theo đối tượng … lệch …” | Tổng các dòng đối tượng không khớp giá trị tổng | Sửa lại để tổng các dòng bằng đúng giá trị tổng |
| “Tổng theo lĩnh vực … lệch …” | Tổng các dòng lĩnh vực không khớp giá trị tổng | Kiểm tra lại từng hệ thống QĐ 36/TT 24 |
| “Giá trị không được âm” | Nhập số âm | Nhập lại số không âm |
| “Nhập một số hợp lệ” | Dùng dấu phẩy thập phân hoặc ký tự lạ | Dùng dấu chấm thập phân, ví dụ `12.5` |
| “Nguồn số liệu không hợp lệ cho chỉ tiêu này” | Chọn nguồn ngoài danh sách được phép | Chọn nguồn khác hoặc bỏ chọn nguồn |
| “Kỳ đã đóng” | Kỳ báo cáo đã bị đóng | Liên hệ Quản trị hệ thống nếu cần điều chỉnh |
| Không thấy dữ liệu của phòng khác | Đúng phạm vi phân quyền | Chỉ xem/nhập cho phòng ban của tài khoản |
| Không thấy menu Duyệt/Danh mục/Quản trị | Không thuộc quyền của Cán bộ nhập liệu | Liên hệ Lãnh đạo phòng/Quản trị khi cần |

---

## 15. Quy tắc dữ liệu cần nhớ

1. **Một hoạt động chỉ nhập số liệu sau khi đã chuyển sang “Đã tổ chức”.**
2. **Lưu nháp** trước, **Gửi duyệt** sau khi đã kiểm tra kỹ.
3. Tổng chỉ tiêu phải khớp với tổng các dòng phân loại.
4. Không nhập số âm; tối đa 4 chữ số thập phân; dùng dấu chấm.
5. Không nhập tay chỉ tiêu tự động tính.
6. Phiếu gửi duyệt/đã duyệt không sửa được.
7. Phiếu bị trả lại phải sửa theo đúng ý kiến rồi gửi lại.
8. Số liệu chính thức trên báo cáo chỉ lấy từ phiếu **Đã duyệt**.
9. Mọi thay đổi số liệu đều được ghi lịch sử.
10. Kiểm tra lại phòng ban, kỳ báo cáo và năm trước khi gửi.

---

## 16. Checklist trước khi gửi duyệt

- [ ] Đã chọn đúng hoạt động/dự án/kỳ báo cáo.
- [ ] Hoạt động đã ở trạng thái **Đã tổ chức**.
- [ ] Đã nhập đủ các chỉ tiêu có nhãn **Bắt buộc**.
- [ ] Tổng các dòng phân loại đối tượng khớp giá trị tổng.
- [ ] Tổng các dòng phân loại lĩnh vực khớp giá trị tổng.
- [ ] Không có giá trị âm, sai định dạng số.
- [ ] Đã chọn nguồn số liệu phù hợp (nếu có).
- [ ] Đã bấm **Lưu nháp** và mở lại kiểm tra (khuyến nghị).
- [ ] Đã đọc lại số liệu lần cuối trước khi bấm **Gửi duyệt**.

---

*Tài liệu này mô tả chức năng hiện có trên website. Khi Quản trị hệ thống thay đổi danh mục, chỉ tiêu hoặc quy trình, hướng dẫn sẽ được cập nhật tương ứng.*
