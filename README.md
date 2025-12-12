## Hướng dẫn cài đặt phần mềm thi trắc nghiệm 
### Bước 1: Cài đặt
- Vào folder ..\installation
- Chạy file `python-3.10.0-amd64.exe` để cài python.(tích vào `add python 3.10 to PATH`)
- Chạy file `xampp-windows-x64-8.0.30-0-VS16-installer.exe` để cài xampp
### Bước 2: Cài dependences
- Chạy lệnh:
`pip install .\libraries\[nhấn tab + enter để cài từng thư viện]`
### Bước 3: Tạo file excel mẫu
chạy file create_template.py để tạo file mẫu excel câu hỏi và trả lời.\
`python create_template.py`
### Bước 4: Tạo database
- Chạy xampp, khởi động 2 service là `Apache` và `MySQL`. 
- Chuột phải vào ô config của apache, chọn `phpMyAdmin (config.inc.php)` để mở file config.
- Tại dòng $cfg['Servers'][$i]['auth_type'], sửa `config` thành 'cookie'
- Mở chrome, vào trang localhost/phpmyadmin, đặt tài khoản mysql là `root`, mật khẩu là `1234`.
- copy file database.sql vào mysql để tạo database.
### Bước 5: Chạy chương trình
`py app.py`