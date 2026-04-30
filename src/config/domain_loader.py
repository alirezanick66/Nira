""" ‫لودر Stateless کانفیگ دامنه‌ها (YAML + Deep Merge + Flatten)"""
from pathlib import Path
from typing import TypeAlias, cast
import yaml
from src.config.logging_config import log_message, LogLevel, LG

# ‫جایگزین Any برای رعایت دقیق قانون ۶ دستورالعمل
ConfigDict: TypeAlias = dict[ str, object ]


class DomainConfigLoader:
    """بارگذار و ادغام‌کنندهٔ پویای فایل‌های کانفیگ دامنه‌ها
    
   ‫ این کلاس کاملاً Stateless طراحی شده تا وابستگی‌ها به‌صورت Dependency Injection
   ‫ به لایه‌های بالاتر تزریق شوند و از State Leakage در محیط‌های هم‌روند جلوگیری گردد.
    """

    def __init__( self, config_dir: Path | str | None = None ) -> None:
        self._config_dir = Path( config_dir ) if config_dir else Path( __file__ ).resolve().parent / "domains"

    def load( self, domain: str = "mobile" ) -> ConfigDict:
        """بارگذاری، ادغام و آماده‌سازی کانفیگ دامنهٔ مشخص‌شده

        Args:
            domain: نام دامنه (پیش‌فرض: mobile)

        Returns:
            دیکشنری ادغام‌شدهٔ آمادهٔ مصرف توسط NLU Pipeline
        """
        base_path = self._config_dir / "base.yaml"
        domain_path = self._config_dir / f"{domain}.yaml"

        if not base_path.is_file():
            raise FileNotFoundError( f"فایل پایهٔ کانفیگ یافت نشد: {base_path}" )
        if not domain_path.is_file():
            raise FileNotFoundError( f"فایل دامنه '{domain}' یافت نشد: {domain_path}" )

        base_cfg = self._read_yaml( base_path )
        domain_cfg = self._read_yaml( domain_path )

        merged = self._deep_merge( base_cfg, domain_cfg )
        self._flatten_qualitative_mappings( merged )

        log_message( LG.NLU, f"✅ کانفیگ دامنه '{domain}' با موفقیت بارگذاری و ادغام شد", LogLevel.INFO )
        return merged

    def _read_yaml( self, path: Path ) -> ConfigDict:
        """ ‫خواندن و اعتبارسنجی اولیهٔ فایل YAML"""
        try:
            with path.open( "r", encoding="utf-8" ) as f:
                data = yaml.safe_load( f )
                if not isinstance( data, dict ):
                    raise ValueError( f"فرمت فایل YAML معتبر نیست (باید دیکشنری باشد): {path}" )
                return cast( ConfigDict, data )
        except yaml.YAMLError as exc:
            log_message( LG.NLU, f"خطا در پارس YAML {path.name}: {exc}", LogLevel.ERROR )
            raise
        except Exception as exc:
            log_message( LG.NLU, f"خطای غیرمنتظره در خواندن {path.name}: {exc}", LogLevel.ERROR )
            raise

    def _deep_merge( self, base: ConfigDict, override: ConfigDict ) -> ConfigDict:
        """ ‫ادغام عمیق دو دیکشنری کانفیگ (override بر base اولویت دارد)"""
        merged = base.copy()
        for key, val in override.items():
            if ( key in merged and isinstance( merged[ key ], dict ) and isinstance( val, dict ) ):
                merged[ key ] = self._deep_merge( cast( ConfigDict, merged[ key ] ), cast( ConfigDict, val ) )
            else:
                merged[ key ] = val
        return merged

    def _flatten_qualitative_mappings( self, config: ConfigDict ) -> None:
        """ ‫تبدیل ساختار گروهی YAML به دیکشنری تخت جهت مصرف سریع پارسر
        
        ورودی YAML:
          price_range:
            budget: [ارزان, ارزون]
        خروجی کد:
          {'ارزان': {'price_range': 'budget'}, 'ارزون': {'price_range': 'budget'}}
        """
        raw = config.get( "qualitative_mappings" )
        if not isinstance( raw, dict ):
            return

        flat: dict[ str, dict[ str, str ] ] = {}
        for filter_key, groups in raw.items():
            if not isinstance( groups, dict ):
                continue
            for value, terms in groups.items():
                if not isinstance( terms, list ):
                    continue
                for term in terms:
                    if isinstance( term, str ):
                        flat[ term ] = { filter_key: value }

        config[ "qualitative_mappings" ] = flat
