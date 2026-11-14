# Hướng dẫn thiết kế biểu mẫu nhập liệu

Tài liệu này dành cho lãnh đạo phòng. Biểu mẫu do phòng thiết kế được dùng khi cán bộ nhập phiếu. Nếu phòng chưa xuất bản biểu mẫu cho một phạm vi, màn hình nhập liệu giữ nguyên form cố định hiện tại.

Chỉ lãnh đạo phòng và quản trị hệ thống được tạo, sửa, xuất bản và lưu trữ. Lãnh đạo trung tâm xem được. Cán bộ nhập liệu không thấy mục **Biểu mẫu**.

## 1. Mở danh sách

1. Đăng nhập bằng tài khoản lãnh đạo phòng.
2. Chọn **Biểu mẫu** trên thanh bên, cạnh **Danh mục**.
3. Trang **Biểu mẫu nhập liệu** liệt kê mẫu của phòng mình. Quản trị hệ thống và lãnh đạo trung tâm có thêm bộ lọc phòng.
4. Lọc theo chức năng (Hoạt động, Chỉ tiêu, Dự án, Báo cáo tháng) và trạng thái (Bản nháp, Đã xuất bản, Đã lưu trữ). Ô tìm kiếm lọc theo tên.

## 2. Tạo biểu mẫu

1. Bấm **Tạo biểu mẫu**.
2. Nhập tên. Chọn chức năng.
3. Chọn phạm vi **Tất cả** hoặc một loại hoạt động / nhóm chỉ tiêu của phòng.
4. Mô tả là tùy chọn. Cán bộ nhập liệu nhìn thấy mô tả này.
5. Bấm lưu. Hệ thống mở màn hình thiết kế, tạo bản nháp phiên bản 1 và một phần **Thông tin chung** cùng các trường hệ thống của chức năng đó.

Mỗi phòng chỉ có một biểu mẫu đang hoạt động cho một phạm vi. Nếu trùng, trang báo **Đã có biểu mẫu đang hoạt động cho phạm vi này.** Hãy lưu trữ biểu mẫu cũ trước khi tạo mẫu mới cùng phạm vi.

## 3. Thêm phần và trường

Màn hình thiết kế có ba vùng: bảng trường bên trái, khung giữa, và bảng thuộc tính bên phải.

1. Bấm **Thêm phần** để tạo một nhóm, ví dụ **Thông tin bổ sung**.
2. Chọn phần trên khung giữa, rồi bấm một kiểu trường ở cột trái. Trường được thêm vào cuối phần đang chọn.
3. Các nhóm kiểu: Cơ bản, Lựa chọn, Ngày giờ, Số, Nâng cao. Có đủ văn bản, đoạn văn, số nguyên, số thập phân, phần trăm, ngày, giờ, ngày giờ, danh sách, chọn nhiều, chọn một, hộp kiểm, công tắc, email, điện thoại, đường dẫn, tệp, ảnh, danh mục và dòng hướng dẫn.
4. **Trường hệ thống** liệt kê trường lõi chưa có trên mẫu. Bấm để đưa lại trường đã gỡ. Trường bắt buộc của hệ thống không gỡ được và không được ẩn hoặc đổi thành không bắt buộc.
5. Bấm một thẻ trường để mở bảng thuộc tính. Các tab: **Chung**, **Dữ liệu**, **Kiểm tra**, **Hiển thị**, **Điều kiện**.
6. Đặt nhãn tiếng Việt, độ rộng từ 1 đến 12, bắt buộc, chỉ đọc, gợi ý, trợ giúp và giá trị mặc định. Mã trường tự sinh và không đổi sau khi tạo.
7. Với danh sách, chọn nhiều hoặc chọn một, thêm ít nhất một lựa chọn đang dùng trước khi xuất bản.
8. Với tệp, khai báo phần mở rộng và dung lượng tối đa (không quá 25 MB). Ảnh chỉ nhận jpg, jpeg, png, gif, webp.
9. Với biểu mẫu chỉ tiêu, trường tùy chỉnh gắn theo từng dòng chỉ tiêu và hiện thêm một cột trên lưới.

Bấm **Áp dụng** hoặc rời ô nhập. Thay đổi được ghi sau khoảng một giây. Thanh trên cùng hiện **Đang lưu…** rồi **Đã lưu lúc HH:MM**. Nếu lỗi, bấm lưu lại.

## 4. Sắp xếp

- Kéo thẻ trường bằng tay nắm để đổi thứ tự trong phần hoặc sang phần khác.
- Dùng nút **Lên**, **Xuống** và **Chuyển phần** nếu không dùng chuột. Các nút này lưu cùng một thứ tự với thao tác kéo.
- Mỗi phần có nút sửa, nhân bản, xóa, lên và xuống.
- Không xóa phần cuối cùng, và không xóa phần còn trường hệ thống bắt buộc.
- Tải lại trang. Thứ tự vừa lưu phải giữ nguyên.

## 5. Điều kiện

Một điều kiện gồm một trường nguồn, một phép so sánh và một hành động cho một trường đích.

Phép so sánh: bằng, khác, chứa, để trống, có giá trị, lớn hơn, lớn hơn hoặc bằng, nhỏ hơn, nhỏ hơn hoặc bằng, thuộc danh sách.

Hành động: hiện, ẩn, bắt buộc, không bắt buộc.

Quy tắc:

- Điều kiện chỉ tác động khi phép so sánh đúng. Không có nhánh “ngược lại”.
- Nhiều điều kiện chạy theo thứ tự. Điều kiện khớp sau ghi đè điều kiện khớp trước.
- Không được trỏ một trường vào chính nó.
- Không được tạo vòng: A làm B bắt buộc và B làm A hiện lại, chẳng hạn.
- Trường hệ thống bắt buộc luôn hiện và luôn bắt buộc.
- Trường đang ẩn không bị kiểm tra bắt buộc. Giá trị đã nhập được giữ nhưng không hiện ở màn xem phiếu.

Ví dụ: khi **Hình thức truyền thông** bằng **Trực tuyến** thì **Đường dẫn phòng họp** là bắt buộc. Giá trị so sánh phải trùng giá trị lưu của lựa chọn, không chỉ trùng nhãn hiển thị nếu hai chuỗi khác nhau.

## 6. Lưu nháp, xem trước và xuất bản

1. **Lưu nháp** ghi tên, mô tả và ghi chú bố cục.
2. **Xem trước** mở đúng form cán bộ nhập liệu sẽ thấy. **Kiểm tra hợp lệ** chạy kiểm tra phía máy chủ.
3. **Xuất bản** mở danh sách kiểm tra. Mẫu cần có tên, ít nhất một phần, ít nhất một trường nhập liệu, nhãn và mã hợp lệ, lựa chọn cho trường chọn, điều kiện không vòng, trường hệ thống bắt buộc còn đủ, biểu thức và giới hạn tệp hợp lệ.
4. Khi đạt, phiên bản nháp trở thành phiên bản đã xuất bản. Hệ thống tạo ngay bản nháp mới với số phiên bản kế tiếp. Cán bộ nhập phiếu mới dùng bản vừa xuất bản. Phiếu đã lưu giữ nguyên phiên bản cũ.
5. Thông báo thành công có dạng **Đã xuất bản phiên bản N**.

Bản đã xuất bản không sửa trực tiếp. Mọi chỉnh sửa sau đó nằm ở bản nháp.

## 7. Phiên bản, nhân bản và lưu trữ

1. Mở **Phiên bản** để xem số phiên bản, trạng thái, người xuất bản, thời điểm và số trường.
2. **Xem** và **Xem trước** chỉ để đọc với bản đã xuất bản.
3. **Tạo bản nháp từ phiên bản này** thay bản nháp hiện tại bằng một bản sao của phiên bản được chọn, sau khi xác nhận. Thao tác này không đổi bản đang dùng cho phiếu mới, và không chạy được nếu bản nháp hiện tại đã có phiếu.
4. **Nhân bản** tạo mẫu cùng phạm vi, tên có hậu tố “(bản sao)”, và để ở trạng thái lưu trữ. Khôi phục bản sao khi muốn dùng nó thay cho mẫu gốc. Nếu mẫu gốc vẫn đang hoạt động, khôi phục báo trùng phạm vi.
5. **Lưu trữ** ẩn mẫu khỏi phiếu mới. Phiếu đã nhập vẫn mở đúng phiên bản và giá trị cũ. **Khôi phục** đưa mẫu trở lại nếu phạm vi chưa có mẫu đang hoạt động khác.

Không xóa phiếu hay phiên bản đã xuất bản từ màn hình này.

## 8. Cách cán bộ nhập liệu thấy mẫu

Cán bộ không chọn mẫu. Hệ thống tự lấy mẫu theo phòng, chức năng và phạm vi của phiếu:

1. Mẫu đúng loại hoạt động hoặc đúng nhóm chỉ tiêu, nếu có và đã xuất bản.
2. Nếu không, mẫu chung của phòng cho chức năng đó.
3. Nếu không có mẫu nào, form cố định như trước.

Khi lưu nháp, trường tùy chỉnh bắt buộc được phép để trống. Khi **Gửi duyệt**, mọi trường đang hiện và đang bắt buộc phải hợp lệ. Nếu thiếu, phiếu ở lại trạng thái nháp và không có dòng lịch sử gửi duyệt. Câu báo lỗi nêu nhãn trường, ví dụ **Vui lòng nhập Số lượng đại biểu.**

Trên phiếu hoạt động, dự án và báo cáo tháng, trường tùy chỉnh nằm theo các phần đã thiết kế, cạnh phần nhập liệu sẵn có. Trên phiếu chỉ tiêu, trường tùy chỉnh là cột thêm của từng dòng. Giá trị đã gửi hiện ở trang chi tiết, hàng chờ duyệt, lịch sử thay đổi và bản in của trang chi tiết.

Trường tùy chỉnh được lưu để xem lại. Bản này chưa cộng chúng vào bảng tổng hợp hay báo cáo Excel/Word.

## 9. Mẫu minh họa

Sau khi đã có phòng HTKN, loại hoạt động **Lớp huấn luyện** và ít nhất một người dùng:

```bash
uv run python manage.py seed_form_templates
```

Lệnh tạo mẫu **Lớp huấn luyện** đã xuất bản, phần **Thông tin bổ sung** gồm số lượng đại biểu, đơn vị chủ trì, hình thức truyền thông, tệp PDF/DOCX, ghi chú, và điều kiện bắt buộc đường dẫn phòng họp khi hình thức là Trực tuyến. Bản nháp kế tiếp có thêm **Ghi chú nội bộ**. Chạy lại lệnh không tạo bản thứ hai.
