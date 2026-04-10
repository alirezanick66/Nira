from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ProductOffer( BaseModel ):
    """‫اطلاعات قیمت و موجودی یک رنگ/فروشنده"""

    # color_name: str | None = None
    # color_code: str | None = None
    price: int = Field( ge=0 )
    discounted_price: int = Field( ge=0 )
    discount_percent: int | None = None
    in_stock: int = Field( default=0, ge=0 )
    stock_text: str | None = None
    delivery_text: str | None = None
    is_techno: bool = False


class ProductSpecs( BaseModel ):
    """‫مشخصات فنی کامل محصول"""

    cpu: str | None = None
    cpu_cores: str | None = None
    gpu: str | None = None
    camera_quality: str | None = None
    os: str | None = None
    release_date: str | None = None
    dimensions_weight: str | None = None
    internal_storage: str | None = None
    ram: str | None = None
    expandable_storage: str | None = None
    display_type: str | None = None
    display_size: str | None = None
    display_colors_resolution: str | None = None
    screen_to_body_ratio: str | None = None
    aspect_ratio: str | None = None
    pixel_density: str | None = None
    multi_touch: str | None = None
    rear_camera: str | None = None
    camera_hardware: str | None = None
    rear_video: str | None = None
    flash: str | None = None
    digital_zoom: str | None = None
    front_camera: str | None = None
    camera_features: str | None = None
    network_internet: str | None = None
    cellular_networks: str | None = None
    umts_speed: str | None = None
    usb_port: str | None = None
    usb_charging: str | None = None
    bluetooth: str | None = None
    audio_jack: str | None = None
    wifi: str | None = None
    wifi_hotspot: str | None = None
    hdmi_output: str | None = None
    gps: str | None = None
    web_browser: str | None = None
    java_support: str | None = None
    music_formats: str | None = None
    audio_recording_formats: str | None = None
    video_formats: str | None = None
    video_recording_formats: str | None = None
    photo_formats: str | None = None
    camera_photo_format: str | None = None
    sensors: str | None = None
    water_dust_resistance: str | None = None
    radio: str | None = None
    other_features: str | None = None
    battery: str | None = None
    battery_capacity: str | None = None
    battery_type: str | None = None
    product_code: str | None = None


class Product( BaseModel ):
    """‫مدل  اصلی محصول """

    # ‫اطلاعات پایه
    product_id: int = Field( description="‫شناسه عددی محصول از URL" )
    name: str
    model: str | None = None
    brand_fa: str | None = None
    brand_en: str | None = None
    category: str | None = None

    # ‫قیمت و موجودی — offer اصلی تکنولایف
    price: int = Field( ge=0 )
    discounted_price: int = Field( ge=0 )
    is_available: bool
    stock_text: str | None = None
    delivery_text: str | None = None

    # ‫همه offer ها (رنگ‌های مختلف)
    offers: list[ ProductOffer ] = Field( default_factory=list )

    # ‫مشخصات فنی
    specs: ProductSpecs = Field( default_factory=ProductSpecs )

    # ‫امتیاز
    score_avg: float | None = Field( default=None, ge=0, le=5 )
    score_count: int | None = Field( default=None, ge=0 )

    # ‫لینک‌ها
    url: str
    image_url: str | None = None

    # ‫زمان scraping
    scraped_at: datetime = Field( default_factory=datetime.utcnow )

    @field_validator( "product_id" )
    @classmethod
    def validate_product_id( cls, value: int ) -> int:
        """‫اعتبارسنجی ID محصول"""
        if value <= 0:
            raise ValueError( "‫product_id باید مثبت باشد" )
        return value
