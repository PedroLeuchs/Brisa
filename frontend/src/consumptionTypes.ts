export interface ConsumptionSettings {
  reference_watts:number|null;
  tariff_per_kwh:number;
  tariff_source:string;
  solar_credits_included:boolean;
}
export interface ConsumptionDay {date:string;on_seconds:number;off_seconds:number;unknown_seconds:number;coverage_percent:number}
export interface ConsumptionSegment {start:number;end:number;state:'on'|'off'|'unknown'}
export interface ConsumptionTransition {start:number;end:number;from:'on'|'off';to:'on'|'off'}
export interface ConsumptionTimelineData {date:string;start:number;end:number;ends_at_now:boolean;sampling_seconds:number;segments:ConsumptionSegment[];transitions?:ConsumptionTransition[]}
export interface ConsumptionDashboard {
  device_id:string;start_date:string;end_date:string;timezone:string;
  collection_started_at:number|null;retained_from:number;
  last_observation:{at:number;power:0|1|null}|null;
  settings:ConsumptionSettings;days:ConsumptionDay[];
  timeline?:ConsumptionTimelineData|null;
  totals:{on_seconds:number;off_seconds:number;unknown_seconds:number;coverage_percent:number;estimated_kwh:number|null;estimated_cost:number|null};
  energy_source:'reference_estimate'|'unavailable';measured_energy_available:boolean;
  method:string;estimate_note:string;
  collector:{status:string;last_check_at:number|null;failures:number;running:boolean;interval_seconds:number};
}
export interface ConsumptionApi {
  consumption(id:string,start:string,end:string):Promise<ConsumptionDashboard>;
  saveConsumptionSettings(id:string,settings:Pick<ConsumptionSettings,'reference_watts'|'tariff_per_kwh'>):Promise<ConsumptionSettings>;
}
