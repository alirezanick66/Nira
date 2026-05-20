"""‫فراخوانی کانفیگ پایه و کانفیگ دامنه و ادغام آن در یک دیکشنری واحد برای مصرف توسط  NLU Pipeline"""
#────────────────────────────────────────── Imports ──────────────────────────────────────────
from pathlib import Path
from typing import cast
from pydantic import BaseModel, Field, computed_field, ConfigDict as PydanticConfig
import yaml

#────────────────────────────────────────── Local  Imports  ──────────────────────────────────────────
from src.config.logging_config import log_message, LogLevel, LG


class DomainConfig( BaseModel ):
    """مدل صریح و اعتبارسنجی‌شده برای پیکربندی دامنه‌ها
    """
    model_config = PydanticConfig( extra="allow" )          # پذیرش فیلدهای دامنه‌های آینده بدون شکست

    #base.yaml Config
    price_ceiling_multiplier: float = Field( default=1.8, description="ضریب سقف هوشمند قیمت نسبت به کف" )
    intent_keywords: dict[ str, dict[ str, list[ str ] ] ] = Field( default_factory=dict )
    qualitative_mappings: dict[ str, dict[ str, list[ str ] ] ] = Field( default_factory=dict )
    slot_definitions: dict[ str, dict[ str, object ] ] = Field( default_factory=dict )
    prompts: dict[ str, object ] = Field( default_factory=dict )

    #mobile.yaml Config
    brands: list[ str ] = Field( default_factory=list )
    categories: list[ str ] = Field( default_factory=list )
    colors: list[ str ] = Field( default_factory=list )
    os_types: list[ str ] = Field( default_factory=list )
    templates: dict[ str, str ] = Field( default_factory=dict )
    use_case_rules: dict[ str, dict[ str, object ] ] = Field( default_factory=dict )
    relaxation_order: list[ str ] = Field( default_factory=list )
    relaxation_mappings: dict[ str, dict[ str, str ] ] = Field( default_factory=dict )
    emphasis_keywords: list[ str ] = Field( default_factory=list )
    filter_cues: dict[ str, list[ str ] ] = Field( default_factory=dict )
    brand_aliases: dict[ str, str ] = Field( default_factory=dict, description="نگاشت مترادف‌های برند به نام کانونیکال" )

    @computed_field
    @property
    def flat_qualitative_mappings( self ) -> dict[ str, dict[ str, str ] ]:
        """تبدیل ساختار گروهی نگاشت‌های کیفی به دیکشنری تخت جهت مصرف سریع در رتریور"""
        flat: dict[ str, dict[ str, str ] ] = {}
        for filter_key, groups in self.qualitative_mappings.items():
            if not isinstance( groups, dict ):
                continue
            for value, terms in groups.items():
                if not isinstance( terms, list ):
                    continue
                for term in terms:
                    if isinstance( term, str ):
                        flat[ term ] = { filter_key: value }
        return flat


class DomainConfigLoader:
    """بارگذار و ادغام‌کنندهٔ پویای فایل‌های کانفیگ دامنه‌ها
    
   ‫ این کلاس کاملاً Stateless طراحی شده تا وابستگی‌ها به‌صورت Dependency Injection
   ‫ به لایه‌های بالاتر تزریق شوند و از State Leakage در محیط‌های هم‌روند جلوگیری گردد.
    """

    def __init__( self, config_dir: Path | str | None = None ) -> None:
        self._config_dir = Path( config_dir ) if config_dir else Path( __file__ ).resolve().parent / "domains"

    #────────────────────────────────────────── Public methods ──────────────────────────────────────────
    def load( self, domain: str = "mobile" ) -> DomainConfig:
        """بارگذاری، ادغام و آماده‌سازی کانفیگ دامنهٔ مشخص‌شده

        Args:
            domain: نام دامنه (پیش‌فرض: mobile)

        Returns:
           ‫ دیکشنری ادغام‌شدهٔ آمادهٔ مصرف توسط NLU Pipeline
        """
        base_path = self._config_dir / "base.yaml"          # فایل پایهٔ مشترک برای همه دامنه‌ها
        domain_path = self._config_dir / f"{domain}.yaml"          # ‫فایل اختصاصی دامنه (مثلاً mobile.yaml)

        if not base_path.is_file():
            raise FileNotFoundError( f"فایل پایهٔ کانفیگ یافت نشد: {base_path}" )
        if not domain_path.is_file():
            raise FileNotFoundError( f"فایل دامنه '{domain}' یافت نشد: {domain_path}" )

        base_cfg = self._read_yaml( base_path )          #خواندن کانفیگ پایه
        domain_cfg = self._read_yaml( domain_path )          #خواندن کانفیگ دامنه

        merged = self._deep_merge( base_cfg, domain_cfg )

        log_message( LG.DATA_PROCESSING, f"✅ کانفیگ دامنه '{domain}' با موفقیت بارگذاری و ادغام شد", LogLevel.INFO )
        return DomainConfig.model_validate( merged )

    #────────────────────────────────────────── Private Methods ──────────────────────────────────────────
    def _read_yaml( self, path: Path ) -> dict[ str, object ]:
        """ ‫خواندن و اعتبارسنجی اولیهٔ فایل YAML

        Args:
            path:‫ مسیر فایل YAML

        Returns:
            دیکشنری پارس‌شده

        Raises:
            yaml.YAMLError: در صورت خطای سینتکس فایل
        """
        try:
            with path.open( "r", encoding="utf-8" ) as f:
                data = yaml.safe_load( f )
                if not isinstance( data, dict ):
                    raise ValueError( f"فرمت فایل YAML معتبر نیست (باید دیکشنری باشد): {path}" )
                return data
        except yaml.YAMLError as exc:
            log_message( LG.DATA_PROCESSING, f"خطا در پارس YAML {path.name}: {exc}", LogLevel.ERROR )
            raise
        except Exception as exc:
            log_message( LG.DATA_PROCESSING, f"خطای غیرمنتظره در خواندن {path.name}: {exc}", LogLevel.ERROR )
            raise

    def _deep_merge( self, base: dict[ str, object ], override: dict[ str, object ] ) -> dict[ str, object ]:
        """ادغام عمیق دو دیکشنری کانفیگ (override بر base اولویت دارد)

        Args:
            base: دیکشنری پایه
            override: دیکشنری جایگزین/تکمیلی

        Returns:
            دیکشنری ادغام‌شده
        """
        merged = base.copy()
        for key, val in override.items():
            if key in merged and isinstance( merged[ key ], dict ) and isinstance( val, dict ):
                merged[ key ] = self._deep_merge( cast( dict[ str, object ], merged[ key ] ), cast( dict[ str, object ], val ) )
            else:
                merged[ key ] = val
        return merged
