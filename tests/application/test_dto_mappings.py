from application.dto import (
    EventTagDTO,
    EventTypeDTO,
    LocationDTO,
    PositionDTO,
    to_event_tag_dto,
    to_event_type_dto,
    to_location_dto,
    to_position_dto,
)
from domain.org.entities import EventTag, EventType, Location, Position
from domain.org.value_objects import (
    Acronym,
    EventTagId,
    EventTagName,
    EventTypeId,
    EventTypeName,
    LocationId,
    LocationName,
    PositionId,
    PositionName,
)


def test_to_location_dto_maps_all_fields():
    loc = Location(
        id=LocationId(1),
        name=LocationName("Centennial Park"),
        description="A nice park",
        latitude=35.1234,
        longitude=-86.5678,
        address_street="123 Main St",
        address_street2="Suite 100",
        address_city="Nashville",
        address_state="TN",
        address_zip="37201",
        address_country="USA",
    )

    dto = to_location_dto(loc)

    assert isinstance(dto, LocationDTO)
    assert dto.id == 1
    assert dto.name == "Centennial Park"
    assert dto.description == "A nice park"
    assert dto.latitude == 35.1234
    assert dto.longitude == -86.5678
    assert dto.address_street == "123 Main St"
    assert dto.address_street2 == "Suite 100"
    assert dto.address_city == "Nashville"
    assert dto.address_state == "TN"
    assert dto.address_zip == "37201"
    assert dto.address_country == "USA"


def test_to_event_type_dto_extracts_value_objects_and_scope():
    et = EventType(
        id=EventTypeId(7),
        name=EventTypeName("Bootcamp"),
        acronym=Acronym("bc"),
        category="first_f",
    )

    dto = to_event_type_dto(et, scope="region")

    assert isinstance(dto, EventTypeDTO)
    assert dto.id == 7
    assert dto.name == "Bootcamp"
    assert dto.acronym == "BC"  # Acronym value object uppercased
    assert dto.category == "first_f"
    assert dto.scope == "region"


def test_to_event_tag_dto_maps_color_and_name():
    tag = EventTag(
        id=EventTagId(3),
        name=EventTagName("CSAUP"),
        color="#ff0000",
    )

    dto = to_event_tag_dto(tag, scope="global")

    assert isinstance(dto, EventTagDTO)
    assert dto.id == 3
    assert dto.name == "CSAUP"
    assert dto.color == "#ff0000"
    assert dto.scope == "global"


def test_to_position_dto_maps_fields_and_scope():
    pos = Position(
        id=PositionId(9),
        name=PositionName("Weasel Shaker"),
        description="Region administrator",
        org_type="region",
    )

    dto = to_position_dto(pos, scope="region")

    assert isinstance(dto, PositionDTO)
    assert dto.id == 9
    assert dto.name == "Weasel Shaker"
    assert dto.description == "Region administrator"
    assert dto.org_type == "region"
    assert dto.scope == "region"
