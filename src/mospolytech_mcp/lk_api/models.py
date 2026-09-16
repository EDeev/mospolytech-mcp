# Модели данных личного кабинета (dataclasses + from_dict-парсинг lk_api.php).

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def flex(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


@dataclass
class Tokens:
    token: str = ""
    jwt: str = ""
    jwt_refresh: str = ""
    guid: str = ""


@dataclass
class TeacherBrief:
    id: int
    name: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TeacherBrief":
        return cls(id=d.get("id") or 0, name=flex(d.get("name")))


@dataclass
class Lesson:
    name: str
    time_interval: str
    place: str
    rooms: list[str]
    teachers: list[str]
    date_interval: str
    link: str
    teachers_full: list[TeacherBrief]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Lesson":
        return cls(
            name=flex(d.get("name")),
            time_interval=flex(d.get("timeInterval")),
            place=flex(d.get("place")),
            rooms=list(d.get("rooms") or []),
            teachers=list(d.get("teachers") or []),
            date_interval=flex(d.get("dateInterval")),
            link=flex(d.get("link")),
            teachers_full=[TeacherBrief.from_dict(t) for t in d.get("teachersFull") or []],
            raw=d,
        )


@dataclass
class ScheduleDay:
    lessons: list[Lesson]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ScheduleDay":
        return cls(lessons=[Lesson.from_dict(x) for x in d.get("lessons") or []])


Schedule = dict[str, ScheduleDay]


def schedule_from_dict(d: dict[str, Any]) -> Schedule:
    return {date: ScheduleDay.from_dict(day) for date, day in d.items()}


@dataclass
class User:
    id: int
    name: str
    surname: str
    patronymic: str
    status: str
    user_status: str
    course: str
    avatar: str
    is_token_valid: bool
    faculty: str
    group: str
    specialty: str
    specialization: str
    code: str
    education_form: str
    finance: str
    degree_level: str
    degree_length: str
    degree_length_std: str
    enter_year: str
    birthday: str
    sex: str
    email: str
    phone: str
    orders: list[str]
    has_alerts: bool
    last_access: str
    pass_expired: bool
    pass_expire_date: str | None
    vacation_start: str | None
    vacation_end: str | None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "User":
        return cls(
            id=d.get("id") or 0,
            name=flex(d.get("name")),
            surname=flex(d.get("surname")),
            patronymic=flex(d.get("patronymic")),
            status=flex(d.get("status")),
            user_status=flex(d.get("user_status")),
            course=flex(d.get("course")),
            avatar=flex(d.get("avatar")),
            is_token_valid=bool(d.get("is_token_valid")),
            faculty=flex(d.get("faculty")),
            group=flex(d.get("group")),
            specialty=flex(d.get("specialty")),
            specialization=flex(d.get("specialization")),
            code=flex(d.get("code")),
            education_form=flex(d.get("educationForm")),
            finance=flex(d.get("finance")),
            degree_level=flex(d.get("degreeLevel")),
            degree_length=flex(d.get("degreeLength")),
            degree_length_std=flex(d.get("degreeLength_standart")),
            enter_year=flex(d.get("enterYear")),
            birthday=flex(d.get("birthday")),
            sex=flex(d.get("sex")),
            email=flex(d.get("email")),
            phone=flex(d.get("phone")),
            orders=list(d.get("orders") or []),
            has_alerts=bool(d.get("hasAlerts")),
            last_access=flex(d.get("lastaccess")),
            pass_expired=bool(d.get("pass_expired")),
            pass_expire_date=d.get("pass_expire_date"),
            vacation_start=d.get("vacation_start"),
            vacation_end=d.get("vacation_end"),
            raw=d,
        )


@dataclass
class PerformanceRecord:
    id: str
    bill_num: str
    bill_type: str
    doc_type: str
    name: str
    exam_date: str
    exam_time: str
    exam_type: str
    grade: str
    ticket_num: str
    teacher: str
    chair: str
    course: str
    year: str
    semester: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PerformanceRecord":
        return cls(
            id=flex(d.get("id")),
            bill_num=flex(d.get("bill_num")),
            bill_type=flex(d.get("bill_type")),
            doc_type=flex(d.get("doc_type")),
            name=flex(d.get("name")),
            exam_date=flex(d.get("exam_date")),
            exam_time=flex(d.get("exam_time")),
            exam_type=flex(d.get("exam_type")),
            grade=flex(d.get("grade")),
            ticket_num=flex(d.get("ticket_num")),
            teacher=flex(d.get("teacher")),
            chair=flex(d.get("chair")),
            course=flex(d.get("course")),
            year=flex(d.get("year")),
            semester=flex(d.get("semestr")),
        )


@dataclass
class Payment:
    date: str
    value: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Payment":
        return cls(date=flex(d.get("date")), value=flex(d.get("value")))


@dataclass
class Agreement:
    id: str
    status: str
    sign_variant: str
    sides: str
    name: str
    type: str
    date: str
    file: str
    reason: str
    code_sent: bool
    can_sign: bool
    signed_user: bool
    signed_user_date: str
    signed_user_time: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Agreement":
        return cls(
            id=flex(d.get("id")),
            status=flex(d.get("status")),
            sign_variant=flex(d.get("sign_variant")),
            sides=flex(d.get("sides")),
            name=flex(d.get("name")),
            type=flex(d.get("type")),
            date=flex(d.get("date")),
            file=flex(d.get("file")),
            reason=flex(d.get("reason")),
            code_sent=bool(d.get("code_sent")),
            can_sign=bool(d.get("can_sign")),
            signed_user=bool(d.get("signed_user")),
            signed_user_date=flex(d.get("signed_user_date")),
            signed_user_time=flex(d.get("signed_user_time")),
        )


@dataclass
class Contract:
    id: str
    number: str
    name: str
    type: str
    level: str
    status_1c: str
    admission: str
    contragent: str
    student: str
    sum: str
    balance: str
    balance_curr_date: str
    last_payment_date: str
    bill: str
    bill_next: str
    qr_current: str
    qr_total: str
    can_sign: bool
    sign_text: str
    sign_variant: str
    signed_user: bool
    signed_user_date: str
    signed_user_time: str
    start_date: str
    end_date_plan: str
    end_date_fact: str
    create_date: str
    file: str
    payments: list[Payment]
    agreements: list[Agreement]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Contract":
        return cls(
            id=flex(d.get("id")),
            number=flex(d.get("number")),
            name=flex(d.get("name")),
            type=flex(d.get("type")),
            level=flex(d.get("level")),
            status_1c=flex(d.get("status1c")),
            admission=flex(d.get("admission")),
            contragent=flex(d.get("contragent")),
            student=flex(d.get("student")),
            sum=flex(d.get("sum")),
            balance=flex(d.get("balance")),
            balance_curr_date=flex(d.get("balance_currdate")),
            last_payment_date=flex(d.get("lastPaymentDate")),
            bill=flex(d.get("bill")),
            bill_next=flex(d.get("bill_next")),
            qr_current=flex(d.get("qr_current")),
            qr_total=flex(d.get("qr_total")),
            can_sign=bool(d.get("can_sign")),
            sign_text=flex(d.get("sign_text")),
            sign_variant=flex(d.get("sign_variant")),
            signed_user=bool(d.get("signed_user")),
            signed_user_date=flex(d.get("signed_user_date")),
            signed_user_time=flex(d.get("signed_user_time")),
            start_date=flex(d.get("startDate")),
            end_date_plan=flex(d.get("endDatePlan")),
            end_date_fact=flex(d.get("endDateFact")),
            create_date=flex(d.get("createDate")),
            file=flex(d.get("file")),
            payments=[Payment.from_dict(p) for p in d.get("payments") or []],
            agreements=[Agreement.from_dict(a) for a in d.get("agreements") or []],
        )


@dataclass
class Payments:
    education: list[Contract]
    dormitory: list[Contract]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Payments":
        return cls(
            education=[Contract.from_dict(c) for c in d.get("education") or []],
            dormitory=[Contract.from_dict(c) for c in d.get("dormitory") or []],
        )


@dataclass
class Notification:
    id: str
    type: str
    title: str
    text: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Notification":
        return cls(
            id=flex(d.get("id")),
            type=flex(d.get("type")),
            title=flex(d.get("title")),
            text=flex(d.get("text")),
        )


@dataclass
class Alert:
    id: str
    title: str
    content: str
    date: str
    time: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Alert":
        return cls(
            id=flex(d.get("id")),
            title=flex(d.get("title")),
            content=flex(d.get("content")),
            date=flex(d.get("date")),
            time=flex(d.get("time")),
        )


@dataclass
class FileRef:
    url: str
    fname: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FileRef":
        return cls(url=flex(d.get("url")), fname=flex(d.get("fname")))


@dataclass
class AppRequest:
    id: str
    num: str
    subject: str
    description: str
    response_div: str
    response_contact: str
    comment: str
    can_delete: bool
    status: str
    raiting: str
    status_update: str
    files_output: list[FileRef]
    created: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AppRequest":
        return cls(
            id=flex(d.get("id")),
            num=flex(d.get("num")),
            subject=flex(d.get("subject")),
            description=flex(d.get("description")),
            response_div=flex(d.get("response_div")),
            response_contact=flex(d.get("response_contact")),
            comment=flex(d.get("comment")),
            can_delete=bool(d.get("can_delete")),
            status=flex(d.get("status")),
            raiting=flex(d.get("raiting")),
            status_update=flex(d.get("status_update")),
            files_output=[FileRef.from_dict(f) for f in d.get("files_output") or []],
            created=flex(d.get("created")),
        )


@dataclass
class DialogueOpponent:
    id: str
    status: str
    name: str
    data: str
    avatar: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DialogueOpponent":
        return cls(
            id=flex(d.get("id")),
            status=flex(d.get("status")),
            name=flex(d.get("name")),
            data=flex(d.get("data")),
            avatar=flex(d.get("avatar")),
        )


@dataclass
class DialogueMessage:
    from_: str
    html: str
    text: str
    datetime: str
    readed: bool
    readed_opponent: bool

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DialogueMessage":
        return cls(
            from_=flex(d.get("from")),
            html=flex(d.get("html")),
            text=flex(d.get("text")),
            datetime=flex(d.get("datetime")),
            readed=bool(d.get("readed")),
            readed_opponent=bool(d.get("readed_opponent")),
        )


@dataclass
class Dialogue:
    id: str
    subject: str
    opponent: DialogueOpponent
    last_message: DialogueMessage

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Dialogue":
        return cls(
            id=flex(d.get("id")),
            subject=flex(d.get("subject")),
            opponent=DialogueOpponent.from_dict(d.get("opponent") or {}),
            last_message=DialogueMessage.from_dict(d.get("lastmessage") or {}),
        )
