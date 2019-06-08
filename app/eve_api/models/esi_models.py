from django.db import models
from django.contrib.auth.models import User
#from eve_api.models import EVEPlayerCharacter
from eve_api.app_defines import *
from raven.contrib.django.raven_compat.models import client as raven_client
from raven import breadcrumbs
import time
import logging

logger=logging.getLogger(__name__)

class CharacterESIRoles(models.Model):
    FIELD_MAPPING = {
        "esi-alliances.read_contacts.v1": "esi_alliances_read_contacts_v1",
        "esi-assets.read_assets.v1": "esi_assets_read_assets_v1",
        "esi-assets.read_corporation_assets.v1": "esi_assets_read_corporation_assets_v1",
        "esi-bookmarks.read_character_bookmarks.v1": "esi_bookmarks_read_character_bookmarks_v1",
        "esi-bookmarks.read_corporation_bookmarks.v1": "esi_bookmarks_read_corporation_bookmarks_v1",
        "esi-calendar.read_calendar_events.v1": "esi_calendar_read_calendar_events_v1",
        "esi-calendar.respond_calendar_events.v1": "esi_calendar_respond_calendar_events_v1",
        "esi-characters.read_agents_research.v1": "esi_characters_read_agents_research_v1",
        "esi-characters.read_blueprints.v1": "esi_characters_read_blueprints_v1",
        "esi-characters.read_contacts.v1": "esi_characters_read_contacts_v1",
        "esi-characters.read_corporation_roles.v1": "esi_characters_read_corporation_roles_v1",
        "esi-characters.read_fatigue.v1": "esi_characters_read_fatigue_v1",
        "esi-characters.read_fw_stats.v1": "esi_characters_read_fw_stats_v1",
        "esi-characters.read_loyalty.v1": "esi_characters_read_loyalty_v1",
        "esi-characters.read_medals.v1": "esi_characters_read_medals_v1",
        "esi-characters.read_notifications.v1": "esi_characters_read_notifications_v1",
        "esi-characters.read_opportunities.v1": "esi_characters_read_opportunities_v1",
        "esi-characters.read_standings.v1": "esi_characters_read_standings_v1",
        "esi-characters.read_titles.v1": "esi_characters_read_titles_v1",
        "esi-characters.write_contacts.v1": "esi_characters_write_contacts_v1",
        "esi-characterstats.read.v1": "esi_characterstats_read_v1",
        "esi-clones.read_clones.v1": "esi_clones_read_clones_v1",
        "esi-clones.read_implants.v1": "esi_clones_read_implants_v1",
        "esi-contracts.read_character_contracts.v1": "esi_contracts_read_character_contracts_v1",
        "esi-contracts.read_corporation_contracts.v1": "esi_contracts_read_corporation_contracts_v1",
        "esi-corporations.read_blueprints.v1": "esi_corporations_read_blueprints_v1",
        "esi-corporations.read_contacts.v1": "esi_corporations_read_contacts_v1",
        "esi-corporations.read_container_logs.v1": "esi_corporations_read_container_logs_v1",
        "esi-corporations.read_corporation_membership.v1": "esi_corporations_read_corporation_membership_v1",
        "esi-corporations.read_divisions.v1": "esi_corporations_read_divisions_v1",
        "esi-corporations.read_facilities.v1": "esi_corporations_read_facilities_v1",
        "esi-corporations.read_fw_stats.v1": "esi_corporations_read_fw_stats_v1",
        "esi-corporations.read_medals.v1": "esi_corporations_read_medals_v1",
        "esi-corporations.read_outposts.v1": "esi_corporations_read_outposts_v1",
        "esi-corporations.read_standings.v1": "esi_corporations_read_standings_v1",
        "esi-corporations.read_starbases.v1": "esi_corporations_read_starbases_v1",
        "esi-corporations.read_structures.v1": "esi_corporations_read_structures_v1",
        "esi-corporations.read_titles.v1": "esi_corporations_read_titles_v1",
        "esi-corporations.track_members.v1": "esi_corporations_track_members_v1",
        "esi-fittings.read_fittings.v1": "esi_fittings_read_fittings_v1",
        "esi-fittings.write_fittings.v1": "esi_fittings_write_fittings_v1",
        "esi-fleets.read_fleet.v1": "esi_fleets_read_fleet_v1",
        "esi-fleets.write_fleet.v1": "esi_fleets_write_fleet_v1",
        "esi-industry.read_character_jobs.v1": "esi_industry_read_character_jobs_v1",
        "esi-industry.read_character_mining.v1": "esi_industry_read_character_mining_v1",
        "esi-industry.read_corporation_jobs.v1": "esi_industry_read_corporation_jobs_v1",
        "esi-industry.read_corporation_mining.v1": "esi_industry_read_corporation_mining_v1",
        "esi-killmails.read_corporation_killmails.v1": "esi_killmails_read_corporation_killmails_v1",
        "esi-killmails.read_killmails.v1": "esi_killmails_read_killmails_v1",
        "esi-location.read_location.v1": "esi_location_read_location_v1",
        "esi-location.read_online.v1": "esi_location_read_online_v1",
        "esi-location.read_ship_type.v1": "esi_location_read_ship_type_v1",
        "esi-mail.organize_mail.v1": "esi_mail_organize_mail_v1",
        "esi-mail.read_mail.v1": "esi_mail_read_mail_v1",
        "esi-mail.send_mail.v1": "esi_mail_send_mail_v1",
        "esi-markets.read_character_orders.v1": "esi_markets_read_character_orders_v1",
        "esi-markets.read_corporation_orders.v1": "esi_markets_read_corporation_orders_v1",
        "esi-markets.structure_markets.v1": "esi_markets_structure_markets_v1",
        "esi-planets.manage_planets.v1": "esi_planets_manage_planets_v1",
        "esi-planets.read_customs_offices.v1": "esi_planets_read_customs_offices_v1",
        "esi-search.search_structures.v1": "esi_search_search_structures_v1",
        "esi-skills.read_skillqueue.v1": "esi_skills_read_skillqueue_v1",
        "esi-skills.read_skills.v1": "esi_skills_read_skills_v1",
        "esi-ui.open_window.v1": "esi_ui_open_window_v1",
        "esi-ui.write_waypoint.v1": "esi_ui_open_window_v1",
        "esi-universe.read_structures.v1": "esi_universe_read_structures_v1",
        "esi-wallet.read_character_wallet.v1": "esi_wallet_read_character_wallet_v1",
        "esi-wallet.read_corporation_wallets.v1": "esi_wallet_read_corporation_wallets_v1",
        "esi-characters.read_chat_channels.v1": "esi_characters_read_chat_channels_v1",
    }

    key = models.OneToOneField('EsiKey', on_delete=models.CASCADE)
    last_updated = models.DateField(auto_now=True)

    esi_alliances_read_contacts_v1 = models.BooleanField(default=False)
    esi_assets_read_assets_v1 = models.BooleanField(default=False)
    esi_assets_read_corporation_assets_v1 = models.BooleanField(default=False)
    esi_bookmarks_read_character_bookmarks_v1 = models.BooleanField(default=False)
    esi_bookmarks_read_corporation_bookmarks_v1 = models.BooleanField(default=False)
    esi_calendar_read_calendar_events_v1 = models.BooleanField(default=False)
    esi_calendar_respond_calendar_events_v1 = models.BooleanField(default=False)
    esi_characters_read_agents_research_v1 = models.BooleanField(default=False)
    esi_characters_read_blueprints_v1 = models.BooleanField(default=False)
    esi_characters_read_contacts_v1 = models.BooleanField(default=False)
    esi_characters_read_corporation_roles_v1 = models.BooleanField(default=False)
    esi_characters_read_fatigue_v1 = models.BooleanField(default=False)
    esi_characters_read_fw_stats_v1 = models.BooleanField(default=False)
    esi_characters_read_loyalty_v1 = models.BooleanField(default=False)
    esi_characters_read_medals_v1 = models.BooleanField(default=False)
    esi_characters_read_notifications_v1 = models.BooleanField(default=False)
    esi_characters_read_opportunities_v1 = models.BooleanField(default=False)
    esi_characters_read_standings_v1 = models.BooleanField(default=False)
    esi_characters_read_titles_v1 = models.BooleanField(default=False)
    esi_characters_write_contacts_v1 = models.BooleanField(default=False)
    esi_characterstats_read_v1 = models.BooleanField(default=False)
    esi_clones_read_clones_v1 = models.BooleanField(default=False)
    esi_clones_read_implants_v1 = models.BooleanField(default=False)
    esi_contracts_read_character_contracts_v1 = models.BooleanField(default=False)
    esi_contracts_read_corporation_contracts_v1 = models.BooleanField(default=False)
    esi_corporations_read_blueprints_v1 = models.BooleanField(default=False)
    esi_corporations_read_contacts_v1 = models.BooleanField(default=False)
    esi_corporations_read_container_logs_v1 = models.BooleanField(default=False)
    esi_corporations_read_corporation_membership_v1 = models.BooleanField(default=False)
    esi_corporations_read_divisions_v1 = models.BooleanField(default=False)
    esi_corporations_read_facilities_v1 = models.BooleanField(default=False)
    esi_corporations_read_fw_stats_v1 = models.BooleanField(default=False)
    esi_corporations_read_medals_v1 = models.BooleanField(default=False)
    esi_corporations_read_outposts_v1 = models.BooleanField(default=False)
    esi_corporations_read_standings_v1 = models.BooleanField(default=False)
    esi_corporations_read_starbases_v1 = models.BooleanField(default=False)
    esi_corporations_read_structures_v1 = models.BooleanField(default=False)
    esi_corporations_read_titles_v1 = models.BooleanField(default=False)
    esi_corporations_track_members_v1 = models.BooleanField(default=False)
    esi_fittings_read_fittings_v1 = models.BooleanField(default=False)
    esi_fittings_write_fittings_v1 = models.BooleanField(default=False)
    esi_fleets_read_fleet_v1 = models.BooleanField(default=False)
    esi_fleets_write_fleet_v1 = models.BooleanField(default=False)
    esi_industry_read_character_jobs_v1 = models.BooleanField(default=False)
    esi_industry_read_character_mining_v1 = models.BooleanField(default=False)
    esi_industry_read_corporation_jobs_v1 = models.BooleanField(default=False)
    esi_industry_read_corporation_mining_v1 = models.BooleanField(default=False)
    esi_killmails_read_corporation_killmails_v1 = models.BooleanField(default=False)
    esi_killmails_read_killmails_v1 = models.BooleanField(default=False)
    esi_location_read_location_v1 = models.BooleanField(default=False)
    esi_location_read_online_v1 = models.BooleanField(default=False)
    esi_location_read_ship_type_v1 = models.BooleanField(default=False)
    esi_mail_organize_mail_v1 = models.BooleanField(default=False)
    esi_mail_read_mail_v1 = models.BooleanField(default=False)
    esi_mail_send_mail_v1 = models.BooleanField(default=False)
    esi_markets_read_character_orders_v1 = models.BooleanField(default=False)
    esi_markets_read_corporation_orders_v1 = models.BooleanField(default=False)
    esi_markets_structure_markets_v1 = models.BooleanField(default=False)
    esi_planets_manage_planets_v1 = models.BooleanField(default=False)
    esi_planets_read_customs_offices_v1 = models.BooleanField(default=False)
    esi_search_search_structures_v1 = models.BooleanField(default=False)
    esi_skills_read_skillqueue_v1 = models.BooleanField(default=False)
    esi_skills_read_skills_v1 = models.BooleanField(default=False)
    esi_ui_open_window_v1 = models.BooleanField(default=False)
    esi_ui_write_waypoint_v1 = models.BooleanField(default=False)
    esi_universe_read_structures_v1 = models.BooleanField(default=False)
    esi_wallet_read_character_wallet_v1 = models.BooleanField(default=False)
    esi_wallet_read_corporation_wallets_v1 = models.BooleanField(default=False)
    esi_characters_read_chat_channels_v1 = models.BooleanField(default=False)

    def reset(self):
        for key in [x for x in self.__class__.__dict__.keys() if x.startswith('esi_')]:
            setattr(self, key, False)
        
        self.save()

    def _get_scope_db_field(self, scope):
        breadcrumbs.record(message="Scope: {}".format(scope))
        if scope not in CharacterESIRoles.FIELD_MAPPING.keys():
            raise AttributeError("Scope {} requested but not in mapping".format(scope))
        
        return CharacterESIRoles.FIELD_MAPPING.get(scope)

    def _check_scope(self, scope):
        if scope not in CharacterESIRoles.FIELD_MAPPING.keys():
            raise AttributeError("Scope {} requested but not in mapping".format(scope))


        db_field_name = self._get_scope_db_field(scope)

        breadcrumbs.record(message="db field: {}".format(db_field_name))
        result = getattr(self, db_field_name, None)

        if result:
            breadcrumbs.record(message="Result: {}".format(result))

        breadcrumbs.record(message="Result: {}".format(result))
        return result

    def _set_scope(self, scope, value):
        db_field_name = self._get_scope_db_field(scope)
        setattr(self, db_field_name, value)

    def update_notify_scopes(self, notify_list):
        scopes = notify_list.split(" ")
        for scope in scopes:
            self._set_scope(scope, True)
        self.save()

    def update_scope(self, scope, value):
        self._set_scope(scope, value)
        self.save()

    def has_scopes(self, names):
        if isinstance(names, list):
            for scope in names:
                if not self._check_scope(scope):
                    return False
            return True
            
        elif isinstance(names, str):
            if not self._check_scope(names):
                breadcrumbs.record(message="has_scopes: {}: {}".format(names, False))
                return False
            else:
                breadcrumbs.record(message="has_scopes: {}: {}".format(names, True))
                return True

