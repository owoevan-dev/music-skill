"""Observable invariants and optional real render/revision tests. Not a taste test."""
import argparse
import importlib
import fnmatch
import json
from pathlib import Path
import time
import traceback
import numpy as np
from make_example import example
from musiclib.model import save_json

# Checks that use what an earlier check left in the work folder: its render, its cache entries or a file it wrote. Found
# by running each check alone (--only) and finding which earlier check's lone run made what was missing. --only runs
# these prerequisites, and theirs, before the checks that need them.
NEEDS={
    'bounded_untrusted_midi_reader':('performed_midi_roundtrip_and_pedal_release',),  # roundtrip.mid
    'loop_cue_points_tempo_and_layer_rules':('loop_fold_points_and_seam',),  # loop_points.wav
    'soundbank_tunes_split_notes_and_quiets_borrowed_dynamics':('split_finds_each_note_of_a_chromatic_run',),  # split_notes/split.json
    'split_reads_a_high_passed_copy_and_leaves_out_takes':('split_finds_each_note_of_a_chromatic_run',),  # the split_source folder
    'bounded_reads_of_records_and_wav_headers':('sf2_writer_reader_roundtrip',),  # tiny.sf2
    'render_folder_is_its_own_run':('actual_render_repeat_is_sample_identical',),  # render_first
    'a_killed_render_resumes':('actual_render_repeat_is_sample_identical',),  # render_first
    'one_note_revision_regenerates_only_its_part':('actual_render_repeat_is_sample_identical',),  # render_first and its cache entries
    'mix_revision_reuses_all_synthesis':('actual_render_repeat_is_sample_identical',),  # render_first and its cache entries
    'bus_chain_render_and_delivery_checks':('actual_render_repeat_is_sample_identical',),  # its cache entries
    'analysis_reports_sections_stems_and_lead':('bus_chain_render_and_delivery_checks',),  # render_bus
    'compare_reports_what_changed_and_where':('bus_chain_render_and_delivery_checks',),  # bus.json, render_bus
    'mix_rules_2_render_limiter_saturation_and_clarity':('bus_chain_render_and_delivery_checks',),  # render_bus
}

def needed(only):
    """The prerequisites, and theirs, of every check the patterns `only` select (NEEDS)."""
    todo=[n for k,v in NEEDS.items() if any(fnmatch.fnmatchcase(k,x) for x in only) for n in v];out=set()
    while todo:
        n=todo.pop()
        if n not in out:out.add(n);todo+=list(NEEDS.get(n,()))
    return out

# The checks in the order they run (0.8 step 1.8): each is defined by area in selfchecks/, and this is the order they
# had in one function.  ROSTER always; ROSTER_CONFIG with a configuration, after it.
AREAS = tuple(importlib.import_module(f'selfchecks.{area}') for area in ('validation', 'midi', 'writing', 'review', 'banks', 'render', 'mix', 'loop', 'revision', 'files', 'setup', 'roll'))
ROSTER = (
    'shared_tempo_clock_and_compound_meter',
    'malformed_projects_rejected',
    'performed_midi_roundtrip_and_pedal_release',
    'more_than_15_melodic_parts_have_distinct_ports',
    'bounded_untrusted_midi_reader',
    'archive_cannot_escape_destination',
    'float_wav_roundtrip',
    'noise_engine_obeys_performance_timing_and_gate',
    'excerpt_preserves_tempo_and_score_bounds',
    'render_patch_and_key_map_leave_export_authored',
    'cc_mode_linear_ramps_continuous_controllers_only',
    'performance_offset_moves_whole_part',
    'pitch_bend_exports_rpn_and_wheel',
    'additive_single_voice_is_centred',
    'review_flags_sustained_minor_ninth',
    'review_vertical_counts_as_0_7_0_did',
    'review_vertical_matches_0_7_0_at_its_edges_and_scale',
    'review_names_embellishing_tones_parallels_and_low_intervals',
    'review_asks_about_loops_returns_arrivals_and_blocks',
    'review_summary_keeps_every_question',
    'review_views_and_identifiers',
    'plan_read_against_score',
    'association_drawn_once',
    'surge_catalog_patch_by_id_search_and_install',
    'sf2_writer_reader_roundtrip',
    'sf2_inventory_reports_keys_layers_seconds_and_loops',
    'soundbank_builds_a_kit_with_microphones_and_choke',
    'soundbank_keeps_recorded_loops_and_evens_takes',
    'soundbank_levels_every_dynamic_of_a_note_together',
    'score_profile_matches_a_hand_counted_line',
    'soundbank_lock_hosts_hashes_and_member_paths',
    'prebuilt_banks_unpack_only_when_they_match_the_lock',
    'bus_assignment_and_validation',
    'church_space_decays_as_specified_and_dynamics_validate',
    'k_weighting_matches_bs1770',
    'loudness_measures_gate_and_compare',
    'true_peak_limiter_holds_the_ceiling',
    'loop_fold_points_and_seam',
    'loop_cue_points_tempo_and_layer_rules',
    'strummed_chords_follow_the_stroke',
    'timing_keeps_to_the_beat_by_phase_correction',
    'soundbank_builds_dynamic_layers_and_legato_presets',
    'soundbank_ring_db_keeps_each_take_to_its_own_decay',
    'soundbank_denoise_keeps_each_layers_partials',
    'split_finds_each_note_of_a_chromatic_run',
    'split_reads_a_high_passed_copy_and_leaves_out_takes',
    'a_soft_take_made_from_the_loud_one',
    'settled_bands_are_closed_once',
    'full_scale_storage_keeps_the_level_heard',
    'stored_patch_changes_the_named_take_alone',
    'the_steinway_patch_is_as_described',
    'the_code_review_of_0_7_stays_fixed',
    'soundbank_tunes_split_notes_and_quiets_borrowed_dynamics',
    'dynamics_crossfade_keeps_power_and_legato_fades_cross',
    'take_mode_learns_brightness_from_the_layers',
    'noise_reduction_lowers_hiss_and_keeps_the_note',
    'click_repair_takes_out_a_knock_and_keeps_the_ring',
    'denoise_keeps_a_soft_low_note_out_of_the_rumble',
    'drum_hits_take_their_recorded_takes_by_their_own_draw',
    'surge_patch_goes_into_the_plugin_state',
    'surge_patch_takes_the_slide_and_accent_the_score_sets',
    'reverse_is_a_sampled_part_rendered_note_by_note',
    'tonal_balance_reads_noise_and_compares_with_a_reference',
    'noise_profile_reads_gated_and_breathy_recordings',
    'split_keeps_the_note_not_its_faint_ring',
    'rubato_slows_phrase_ends_and_the_close',
    'swing_delays_off_beats_and_keeps_the_beat',
    'round_robins_bow_changes_and_portamento',
    'a_bell_facing_back_sounds_darker_and_further',
    'phrasing_helpers_arch_swell_and_hold',
    'voicing_moves_smoothly_and_spaces_chords',
    'building_blocks_write_parts_from_the_pieces_settings',
    'building_blocks_add_blasts_grids_skank_pompe_batida_slides',
    'style_maps_set_reviews_limits_by_axis',
    'dance_styles_ask_about_loops_only_where_nothing_moves',
    'brightness_prompts_follow_the_genre_and_the_low_passes',
    'style_tempo_ranges_ask_outside_their_sources',
    'synth_is_band_limited_stable_and_repeatable',
    'drum_machine_voices_kick_pitch_drop_and_gated_snare',
    'drum_machine_render_places_chokes_and_tunes_the_kit',
    'production_delay_duck_gate_and_mono_low_end',
    'part_saturation_keeps_loudness_and_adds_harmonics',
    'chip_arpeggio_stepped_triangle_and_clocked_noise',
    'synth_pitch_envelope_punches_and_settles',
    'tape_wow_flutter_and_vinyl_noise',
    'chorus_reads_its_moving_delay_between_samples',
    'stage_depth_moves_reflections_and_hall',
    'expressive_fields_validate',
    'validation_holds_its_limits_at_their_edges',
    'effects_are_capped_per_part_and_counted_as_listed',
    'range_control_lifts_soft_passages_only',
    'review_flags_far_transposed_samples_and_missing_keys',
    'a_piano_part_on_another_piano_is_asked_about',
    'analysis_groups_octave_doublings_and_suggests_cuts',
    'analysis_names_the_parts_that_carry_the_top',
    'integer_fields_and_unknown_fields_are_reported',
    'synthesis_cache_follows_the_played_tempo',
    'slow_rubato_reads_back_from_its_midi',
    'drum_parts_get_their_own_ports',
    'phrase_arches_follow_the_meter',
    'excerpt_moves_bends_sweeps_and_dynamics',
    'a_long_mono_line_starts_afresh_after_thirty_seconds',
    'fluidsynth_diagnostics_ignore_its_paths',
    'a_cut_manifest_writes_only_inside_its_folder',
    'inspect_midi_keeps_its_input',
    'a_config_written_elsewhere_keeps_relative_banks',
    'a_short_or_damaged_download_is_never_kept',
    'compare_finds_level_and_local_changes',
    'compare_reports_no_level_for_a_rewritten_file',
    'cache_entry_locked_across_renders',
    'clean_removes_only_what_the_tools_made',
    'cache_entries_go_by_their_own_record',
    'files_never_overwrite_or_write_through',
    'journal_proves_a_stopped_run',
    'writers_leave_whole_files_when_a_write_fails',
    'run_stops_its_program_when_stopped',
    'bootstrap_receipts_set_aside_what_it_did_not_write',
    'clean_and_runs_never_share_a_folder',
    'render_refuses_a_linked_output',
    'bounded_reads_of_records_and_wav_headers',
    'wav_readers_decode_each_encoding_and_keep_their_header_rules',
    'wav_readers_keep_their_policies_on_the_same_bytes',
    'project_text_stays_text',
    'bank_files_named_by_template',
    'bank_build_opens_no_link_below_its_root',
    'bank_cut_checks_each_span_first',
    'aiff_reader_walks_headers_and_refuses_what_it_cannot_hold',
    'json_read_with_a_byte_order_mark',
    'sounds_search_names_what_it_does_not_know',
    'every_command_has_help_and_an_example',
    'messages_say_where_what_and_the_rule',
    'instruments_reads_keys_and_layers_from_the_bank',
    'own_folder_and_sfz_build_banks',
    'builder_keeps_the_books_and_start_writes_a_valid_piece',
    'aiff_reader_decodes_each_kind_it_takes',
    'slur_legato_plays_one_line',
    'synth_modulation_in_beats_follows_the_tempo',
    'json_output_survives_an_ascii_console',
    'delete_sources_takes_only_the_installers_files',
    'flac_source_must_be_flac',
    'notes_csv_escapes_formulas',
    'shared_reports_name_folders_relatively',
    'scripts_escape_what_their_output_cannot_show',
    'pedalboard_checked_against_its_record',
    'automation_applies_per_sample_with_held_ends',
    'swing_pairs_counted_from_each_bar_line',
    'excerpt_keeps_the_piece_at_its_edges',
    'tick_rounding_is_stable',
    'soundfont_tables_must_hold_together',
    'sf2_tables_are_refused_by_their_size',
    'sf2_tables_may_end_without_their_terminal_records',
    'sf2_reader_refuses_early_and_keeps_its_forms',
    'parts_wait_for_memory',
    'selfcheck_work_must_be_new_or_empty',
    'source_listing_must_name_the_pinned_samples',
    'pedalboard_wheel_fetched_by_its_lock',
    'render_folders_are_read_without_links',
    'a_part_larger_than_the_machine_is_refused',
    'piano_roll_draws_the_notes_as_played',
    'long_paths_reach_programs_in_a_form_they_open',
    'a_part_moves_by_one_gain_for_each_channel',
    'an_amplifier_makes_one_signal_of_a_parts_notes',
    'a_part_played_by_string_is_checked_and_strummed_by_string',
    'a_stem_too_faint_to_measure_is_silent',
    'a_headphone_version_places_every_part',
    'a_draft_takes_a_tail_that_still_sounds_as_a_note',
    'review_asks_about_a_kit_levelled_by_its_peak',
    'review_counts_seconds_and_ninths_and_asks_about_the_exposed',
    'review_sets_apart_runs_of_doubling_and_pitchless_patches',
    'a_video_over_its_size_is_encoded_again_lower',
)
ROSTER_CONFIG = (
    'render_cache_checks_each_take_before_using_it',
    'preset_list_keys_match_the_banks',
    'actual_render_repeat_is_sample_identical',
    'render_folder_is_its_own_run',
    'a_killed_render_resumes',
    'one_note_revision_regenerates_only_its_part',
    'mix_revision_reuses_all_synthesis',
    'kept_stems_follow_what_they_read',
    'dependency_hash_mismatch_stops_before_render',
    'bank_lsb_selects_bank_on_default_soundfont',
    'named_soundfont_selected_per_track',
    'named_bank_verified_at_first_use',
    'pitch_bend_moves_soundfont_pitch',
    'legato_slurs_and_width_render',
    'bus_chain_render_and_delivery_checks',
    'a_chorus_pass_never_shares_another_parts_log',
    'effects_apply_in_the_order_listed',
    'a_reversed_note_swells_into_its_end',
    'analysis_reports_sections_stems_and_lead',
    'compare_reports_what_changed_and_where',
    'loop_render_folds_the_tail_into_wav_and_ogg',
    'loop_layers_render_and_add_up_to_the_mix',
    'mix_rules_2_render_limiter_saturation_and_clarity',
    'wide_dynamics_master_keeps_the_mix_range',
    'layered_render_slurs_and_crossfades_dynamics',
    'take_dynamics_play_one_recorded_dynamic_per_note',
    'stage_depth_and_range_control_render',
    'surge_part_plays_the_patch_or_its_fallback',
    'audition_plays_one_part_on_several_sounds',
    'revision_rounds_and_clean',
    'outputs_carry_no_input_metadata',
    'flac_sources_decode_within_a_limit',
    'a_silent_part_is_named',
    'long_automation_renders',
    'piano_roll_video_carries_the_master',
    'cache_entries_have_short_names_and_whole_keys',
    'the_paths_below_a_piece_stay_short',
    'a_render_in_a_deep_folder_gives_the_same_master',
    'a_video_in_a_deep_folder_is_made',
    'a_moving_part_renders_and_the_others_stay',
    'a_part_through_an_amplifier_renders_and_the_others_stay',
    'a_part_played_by_string_renders_string_by_string',
    'a_headphone_version_renders_beside_the_master',
    'a_draft_render_notes_its_tail_and_a_full_render_fails',
    'another_skill_reads_the_configuration_and_doctor',
    'a_failed_pass_leaves_no_scratch_file',
)

def checks(work,config=None,only=None,keep_going=False):
    """Run the checks into `work`.  `only`: fnmatch patterns; a check whose name matches none is skipped (its function
    is not called; the code between checks still runs, so what they share is still made), unless a selected check
    needs it (NEEDS).  `keep_going`: a failing check is recorded with its error and the run goes on, so one run names
    every failure; by default the first failure stops the run, as it always has."""
    work=Path(work).resolve();work.mkdir(parents=True,exist_ok=True);results=[];skipped=[]
    prerequisites=needed(only) if only is not None else set();order=[]
    def check(name,fn):
        order.append(name)
        if only is not None and name not in prerequisites and not any(fnmatch.fnmatchcase(name,pattern) for pattern in only):
            skipped.append(name);return
        began=time.monotonic()
        try:
            details=fn();results.append({'name':name,'passed':True,'details':details,'seconds':round(time.monotonic()-began,3)})
            print('PASS',name,flush=True)
        except Exception as e:
            results.append({'name':name,'passed':False,'error':repr(e)})
            if not keep_going:
                save_json(work/'selfcheck_report.json',{'status':'FAIL','checks':results});raise
            results[-1]['traceback']=traceback.format_exc(limit=-4)[-3000:];print('FAIL',name,repr(e)[:300],flush=True)
    def rejects(fn):
        try:fn()
        except ValueError:return True
        raise AssertionError('Expected rejection')
    def rejects_with(kind,fn):
        try:fn()
        except kind:return True
        raise AssertionError(f'Expected {kind.__name__}')
    def xf_bank():
        """A two-dynamic sustained instrument (a soft sine and a bright tone, both swelling in over 300 ms, as a bowed
        attack does) with dynamic-layer and legato presets; built once per selfcheck."""
        import wave
        from soundbank import build
        path=work/'xf.sf2'
        if path.is_file():return path
        root=work/'xf_source';root.mkdir(parents=True,exist_ok=True);rate=48000;t=np.arange(3*rate)/rate;ramp=np.minimum(1,t/.3)
        for name,f0 in (('C4',261.63),('G4',392.0)):
            for dyn,x in (('p',.1*ramp*np.sin(2*np.pi*f0*t)),('f',.3*ramp*sum(np.sin(2*np.pi*f0*h*t)/h for h in range(1,9)))):
                q=np.clip(np.round(np.repeat(x[:,None],2,1)*32767),-32768,32767).astype('<i2')
                with wave.open(str(root/f'x_{name}_{dyn}.wav'),'wb') as w:w.setnchannels(2);w.setsampwidth(2);w.setframerate(rate);w.writeframes(q.tobytes())
        layer={'dir':'.','template':'x_{note}_{dyn}.wav','dynamics':['p','f'],'velocity':{'p':[1,64],'f':[65,127]},
               'keys':[55,72],'layer_levels_db':{'p':-9,'f':0},'envelope':{'attack':.005,'release':.3}}
        preset={'name':'held','program':48,'layers':[layer],'dynamic_layers':{'bank':16},'legato':{'bank':32,'attack':.01}}
        build({'name':'xf','presets':[preset]},root,path)
        plain={k:v for k,v in preset.items() if k not in ('dynamic_layers','legato')}
        build({'name':'xf','presets':[plain]},root,work/'xf_plain.sf2')
        return path
    # The checks are defined by area in selfchecks/ and run here in one order, as they ran when they lived in this
    # function (0.8 step 1.8): ROSTER, then with a configuration ROSTER_CONFIG, whose checks share the example
    # render's project and cache, made where their block began.  What a check shares with the others comes in S.
    S={'work':work,'config':config,'rejects':rejects,'rejects_with':rejects_with,'xf_bank':xf_bank}
    # Made before ROSTER since the split (one function made it after): where making it fails (a fault in validate),
    # ROSTER still runs and each check of the block fails by name with that error, so the report is written (the third
    # outside review found the whole run stopping with none).
    setup=None
    if config:
        try:
            from musiclib.render import render
            S.update(render=render,p=example(),cache=work/'cache')
        except Exception as e:
            setup=e
    found={}
    for area in AREAS:found.update(area.define({**S,'config':None} if setup else S))
    for name in ROSTER:check(name,found[name])
    if config:
        if setup is None:save_json(work/'example.json',S['p'])   # the code between checks runs whatever --only selects
        for name in ROSTER_CONFIG:check(name,found.get(name) or (lambda e=setup:(_ for _ in ()).throw(e)))
    # NEEDS names checks that exist and come before the ones that need them (a misspelt name would quietly do nothing).
    late=[(k,n) for k in NEEDS if k in order for n in NEEDS[k] if n not in order or order.index(n)>order.index(k)]
    if late:raise ValueError(f'NEEDS names a check that is missing or comes later: {late}')
    report={'status':'PASS' if all(r['passed'] for r in results) else 'FAIL','checks':results,'render_checks_included':bool(config),'direct_audio_audition':False,'musical_quality_certified':False}
    if only is not None:
        names=[r['name'] for r in results]+skipped
        report.update(only=list(only),prerequisites=sorted(prerequisites),skipped=len(skipped),
                      unmatched=[x for x in only if not any(fnmatch.fnmatchcase(n,x) for n in names)])
    save_json(work/'selfcheck_report.json',report);return report

if __name__=='__main__':
    import sys
    from musiclib import files
    files.escape_unprintable()
    p=argparse.ArgumentParser(description='Run the skill\'s checks: each one tests an invariant (validation, rendering, mixing, the tools); none judges taste.')
    p.add_argument('--work',type=Path,required=True,help='a new or empty folder for everything the checks write')
    p.add_argument('--config',type=Path,help='a renderer configuration (bootstrap.py writes one); without it the checks that render are left out')
    p.add_argument('--only',action='append',metavar='PATTERNS',help='run only the checks whose names match one of these comma-separated fnmatch patterns, e.g. "loop_*,revision_rounds_and_clean"; repeatable')
    p.add_argument('--keep-going',action='store_true',help='run every check and report all that fail, instead of stopping at the first failure')
    args=p.parse_args()
    only=[x.strip() for v in (args.only or []) for x in v.split(',') if x.strip()] or None
    # The checks write many files under fixed names, so the folder must be new or empty: a report there or not, what
    # it already holds is not theirs to overwrite.
    if files.linked(args.work) or (files.occupied(args.work) and (not args.work.is_dir() or any(args.work.iterdir()))):
        print(f'ERROR: --work {args.work} is not empty (or is a link); give a new or empty folder (the selfcheck writes many files there)',file=sys.stderr)
        sys.exit(2)
    result=checks(args.work,args.config,only=only,keep_going=args.keep_going)
    failed=[r['name'] for r in result['checks'] if not r['passed']]
    print(json.dumps({'status':result['status'],'checks':len(result['checks']),**({'failed':failed} if failed else {}),**({'skipped':result['skipped']} if only else {})}),flush=True)
    if only and result['unmatched']:
        print(f'ERROR: --only matched no check for {", ".join(result["unmatched"])}; the names are in selfcheck_report.json of a full run',file=sys.stderr)
        sys.exit(2)
    if failed:sys.exit(1)
