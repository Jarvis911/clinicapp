from app.models import (User, BenhNhan, Thuoc, PhieuKham, DonThuoc, BacSi, UserRole,
                        DonViThuoc, HoaDon, QuyDinh, ThuNgan, DangKyKham, DsKham, LoaiThuoc)
from datetime import datetime
from app import app, db
from typing import cast
import hashlib
from sqlalchemy import and_, func, distinct
from sqlalchemy.types import Date
import cloudinary.uploader
from flask_login import current_user
from sqlalchemy.orm import aliased


def get_user_by_id(id):
    return User.query.get(id)


def load_medicines_unit():
    units = DonViThuoc.query.all()  # Lấy tất cả các đơn vị thuốc
    return {unit.id: {"name": unit.name} for unit in units}


def load_patients(kw=None):
    query = BenhNhan.query.join(PhieuKham, PhieuKham.id_benh_nhan == BenhNhan.id, isouter=True) \
        .filter(PhieuKham.id.is_(None))

    if kw:
        query = query.filter(BenhNhan.name.contains(kw))

    return query.all()

def load_user_role():
    return UserRole

def load_medicines(kw=None):
    query = Thuoc.query

    if kw:
        query = query.filter(Thuoc.name.contains(kw))

    return query.all()


def auth_user(username, password, role=None):
    password = str(hashlib.md5(password.strip().encode('utf-8')).hexdigest())
    u = User.query.filter(User.username.__eq__(username.strip()),
                          User.password.__eq__(password))

    if role:
        u = u.filter(User.user_role.__eq__(role))

    return u.first()


def add_phieukham(phone, datetime, trieu_chung, du_doan_benh, cart):
        # Tìm bệnh nhân theo số điện thoại
        patient = BenhNhan.query.filter(BenhNhan.phone.__eq__(phone)).first()
        if not patient:
            return {"message": "Bệnh nhân không tồn tại trong hệ thống."}, 404

        # Lấy thông tin bác sĩ từ current_user (Flask-Login)
        bac_si_id = current_user.id  # Bác sĩ hiện tại

        # Tạo mới phiếu khám
        new_phieu_kham = PhieuKham(
            bac_si_id=bac_si_id,
            id_benh_nhan=patient.id,
            date_kham=datetime,
            trieu_chung=trieu_chung,
            du_doan_benh=du_doan_benh,
            da_xuat_hoa_don=False
        )

        db.session.add(new_phieu_kham)
        db.session.commit()

        # Thêm đơn thuốc nếu có
        for d in cart.values():
            thuoc = Thuoc.query.filter(Thuoc.id == d['id']).first()
            if thuoc:
                don_thuoc = DonThuoc(
                    phieu_kham_id=new_phieu_kham.id,
                    thuoc_id=thuoc.id,
                    quantity=d['quantity'],
                    cach_dung=d['cach_dung']
                )
                db.session.add(don_thuoc)

        db.session.commit()

        return {"message": "Phiếu khám và đơn thuốc đã được thêm thành công!"}, 201


def load_unpaid_phieukham():
    unpaid_phieukham = db.session.query(
        PhieuKham.id,
        PhieuKham.date_kham,
        BenhNhan.name.label('benh_nhan_name')
    ).join(BenhNhan, PhieuKham.id_benh_nhan == BenhNhan.id).filter(
        PhieuKham.da_xuat_hoa_don == False
    ).all()

    return unpaid_phieukham


def tao_hoa_don(phieu_kham_id):
    # Lấy phiếu khám từ ID
    phieu_kham = PhieuKham.query.get(phieu_kham_id)
    if not phieu_kham:
        raise ValueError("Phiếu khám không tồn tại.")

    #Kiểm tra xem hóa đơn được tạo chưa
    existing_hoa_don = HoaDon.query.filter_by(phieu_kham_id=phieu_kham.id).first()
    if existing_hoa_don:
        raise ValueError("Hóa đơn đã được tạo cho phiếu khám này.")

    # Lấy quy định hệ thống (mặc định chỉ có 1 dòng trong bảng QuyDinh)
    quy_dinh = QuyDinh.query.first()
    if not quy_dinh:
        raise ValueError("Không tìm thấy quy định hệ thống.")

    # Tính tổng tiền thuốc
    tong_tien_thuoc = 0
    for don_thuoc in phieu_kham.thuoc:  # Lặp qua các đơn thuốc của phiếu khám
        if don_thuoc.thuoc:  # Kiểm tra xem đơn thuốc có liên kết với thuốc không
            tong_tien_thuoc += don_thuoc.quantity * don_thuoc.thuoc.price  # Cộng dồn giá * số lượng

    # Tạo hóa đơn
    hoa_don = HoaDon(
        quy_dinh_id=quy_dinh.id,  # Liên kết với quy định hiện tại
        phieu_kham_id=phieu_kham.id,
        thu_ngan_id=current_user.id,  # ID người thu ngân là current user
        tong_tien=tong_tien_thuoc + quy_dinh.examineFee  # Tổng tiền = tiền thuốc + tiền khám
    )
    db.session.add(hoa_don)

    # Cập nhật trạng thái phiếu khám
    phieu_kham.da_xuat_hoa_don = True

    # Lưu vào DB
    db.session.commit()

    return hoa_don

def get_phieu_kham_id(phieu_kham_id):
    return PhieuKham.query.get(phieu_kham_id)

def get_tien_kham():
    quy_dinh = QuyDinh.query.first()
    tien_kham = quy_dinh.examineFee
    return tien_kham


def get_thu_ngan_name():
    thu_ngan = ThuNgan.query.get(current_user.id)
    return thu_ngan.name

def get_benh_nhan_name(phieu_kham_id):
    phieu_kham = PhieuKham.query.get(phieu_kham_id)
    benh_nhan = BenhNhan.query.get(phieu_kham.id_benh_nhan)

    return benh_nhan.name

def get_benh_nhan_name_phieudk(dang_ky_kham_id):
    dang_ky_kham = DangKyKham.query.get(dang_ky_kham_id)
    benh_nhan = BenhNhan.query.get(dang_ky_kham.id_benh_nhan)

    return benh_nhan.name

def get_benh_nhan_phone_phieudk(dang_ky_kham_id):
    dang_ky_kham = DangKyKham.query.get(dang_ky_kham_id)
    benh_nhan = BenhNhan.query.get(dang_ky_kham.id_benh_nhan)

    return benh_nhan.phone

def get_tong_tien_thuoc(phieu_kham_id):
    phieu_kham = PhieuKham.query.get(phieu_kham_id)
    quy_dinh = QuyDinh.query.first()
    tong_tien_thuoc = 0
    for don_thuoc in phieu_kham.thuoc:  # Lặp qua các đơn thuốc của phiếu khám
        if don_thuoc.thuoc:  # Kiểm tra xem đơn thuốc có liên kết với thuốc không
            tong_tien_thuoc += don_thuoc.quantity * don_thuoc.thuoc.price  # Cộng dồn giá * số lượng

    return tong_tien_thuoc + quy_dinh.examineFee


def load_doctors():
    return BacSi.query.all()

def add_ExamineForm(phone,name, birth, gender, email, appointment_date):

    patient = BenhNhan.query.filter(BenhNhan.phone.__eq__(phone)).first()
    if not patient:
        patient = BenhNhan(
            name=name,
            phone=phone,
            birth=birth,
            gender=gender,
            email=email,

        )
        db.session.add(patient)
        db.session.commit()

    new_DangKyKham = DangKyKham(
        benhNhan_id=patient.id,
        appointment_date=appointment_date,
        created_date=datetime.now(),
        state=False
    )
    db.session.add(new_DangKyKham)
    db.session.commit()

    return "Đăng kí khám đã được ghi nhận, xin vui lòng chờ mail từ chúng tôi!"



#LAP DANH SACH KHAM
def get_phieu_list(date):
    # Đảm bảo định dạng của `date` đầu vào là datetime
    date_obj = datetime.strptime(date, '%Y-%m-%d')  # Chuyển chuỗi `date` về datetime

    # Tạo alias cho bảng BenhNhan
    BenhNhanAlias = aliased(BenhNhan)

    # Truy vấn kết hợp hai bảng
    phieus = db.session.query(
        DangKyKham.id,
        DangKyKham.appointment_date,
        BenhNhanAlias.name.label('benh_nhan_name'),
        BenhNhanAlias.phone.label('benh_nhan_phone')
    ).join(
        BenhNhanAlias, DangKyKham.benhNhan_id == BenhNhanAlias.id
    ).filter(
        DangKyKham.state == 0,
        DangKyKham.appointment_date == date_obj
    ).all()

    # Chuyển kết quả thành danh sách dictionary
    result = [
        {
            "phieu_id": phieu.id,
            "appointment_date": phieu.appointment_date,
            "benh_nhan_name": phieu.benh_nhan_name,
            "benh_nhan_phone": phieu.benh_nhan_phone
        }
        for phieu in phieus
    ]

    # Debug log kết quả
    print(f"Filtered phieus with patient info: {result}")

    return result

def add_ds_kham(phieu_ids):

    y_ta_id = current_user.id
    num_phieu_to_add = len(phieu_ids)

    maxPatients = QuyDinh.query.first().maxPatient

    if num_phieu_to_add > maxPatients:
        raise ValueError(f"Số lượng phiếu đăng ký vượt quá giới hạn cho phép ({maxPatients}).")


    # Tạo một danh sách khám mới
    danh_sach_kham = DsKham(y_ta_id=y_ta_id, created_date=datetime.now())


    db.session.add(danh_sach_kham)
    db.session.flush()  # Lưu tạm để lấy `id` của danh sách khám


    # Cập nhật các phiếu đăng ký được chọn
    DangKyKham.query.filter(DangKyKham.id.in_(phieu_ids)).update(
        {DangKyKham.dsKham_id: danh_sach_kham.id,
         DangKyKham.state: True}, synchronize_session=False
    )

    db.session.commit()

    #THONG KE

def revenue_stats_by_time(month=datetime.now().month, year=datetime.now().year):
    stats = db.session.query(
        func.extract('day', PhieuKham.date_kham).label('day'),  # Lấy ngày từ cột date_kham
        func.sum(HoaDon.tong_tien),  # Tính tổng doanh thu
        func.count(func.distinct(PhieuKham.id_benh_nhan))  # Đếm số bệnh nhân trong ngày (dùng distinct)
    ) \
        .join(HoaDon, HoaDon.phieu_kham_id == PhieuKham.id) \
        .filter(func.extract('year', PhieuKham.date_kham) == year) \
        .filter(func.extract('month', PhieuKham.date_kham) == month) \
        .group_by(func.extract('day', PhieuKham.date_kham)) \
        .order_by(func.extract('day', PhieuKham.date_kham)).all()

    # Lấy tổng doanh thu của tháng
    total_revenue = db.session.query(func.sum(HoaDon.tong_tien))\
        .join(PhieuKham, HoaDon.phieu_kham_id == PhieuKham.id)\
        .filter(func.extract('year', PhieuKham.date_kham) == year)\
        .filter(func.extract('month', PhieuKham.date_kham) == month)\
        .scalar()

    return stats, total_revenue

def medicine_statistics(month, year):
    stats = db.session.query(
        Thuoc.name.label('medicine_name'),  # Tên thuốc
        DonViThuoc.name.label('unit_name'),  # Tên đơn vị
        func.sum(DonThuoc.quantity).label('total_quantity')  # Tổng số lượng kê đơn
    )\
    .join(DonThuoc, DonThuoc.thuoc_id == Thuoc.id)\
    .join(DonViThuoc, DonViThuoc.id == Thuoc.unit_id)\
    .join(PhieuKham, PhieuKham.id == DonThuoc.phieu_kham_id)\
    .filter(func.extract('month', PhieuKham.date_kham) == month)\
    .filter(func.extract('year', PhieuKham.date_kham) == year)\
    .group_by(Thuoc.name, DonViThuoc.name)\
    .order_by(Thuoc.name).all()

    return stats
