from pydantic import BaseModel, Field

# --- WebUntis API response models ---


class UntisElement(BaseModel):
    type: int
    id: int
    name: str = ""
    long_name: str = Field("", alias="longName")
    display_name: str = Field("", alias="displayname")


class UntisElementRef(BaseModel):
    type: int
    id: int
    org_id: int = Field(0, alias="orgId")
    missing: bool = False
    state: str = "REGULAR"


class UntisElementWrapper(BaseModel):
    element: UntisElement


class UntisPeriod(BaseModel):
    id: int
    date: int
    start_time: int = Field(alias="startTime")
    end_time: int = Field(alias="endTime")
    lesson_text: str = Field("", alias="lessonText")
    subst_text: str = Field("", alias="substText")
    cell_state: str = Field("STANDARD", alias="cellState")
    elements: list[UntisElementRef] = []
    subjects: list[UntisElementWrapper] = []
    teachers: list[UntisElementWrapper] = []
    classes: list[UntisElementWrapper] = []
    rooms: list[UntisElementWrapper] = []
