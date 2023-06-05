# Released under the MIT License. See LICENSE for details.
#
"""Generates parts of babase._app.py.

This includes things like subsystem attributes for all feature-sets that
define them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from efro.error import CleanError

if TYPE_CHECKING:
    from batools.featureset import FeatureSet


def generate_app_module(
    feature_sets: dict[str, FeatureSet], existing_data: str
) -> str:
    """Generate babase._app.py based on its existing version."""

    # pylint: disable=too-many-locals
    import textwrap

    from efrotools import replace_section

    out = ''

    fsets = feature_sets

    out = existing_data

    info = f'# This section generated by {__name__}; do not edit.'
    indent = '    '

    # Import modules we need for feature-set subsystems.
    contents = ''
    for _fsname, fset in sorted(fsets.items()):
        if fset.has_python_app_subsystem:
            modname = fset.name_python_package
            classname = f'{fset.name_camel}Subsystem'
            contents += f'from {modname} import {classname}\n'
    out = replace_section(
        out,
        f'{indent}# __FEATURESET_APP_SUBSYSTEM_IMPORTS_BEGIN__\n',
        f'{indent}# __FEATURESET_APP_SUBSYSTEM_IMPORTS_END__\n',
        textwrap.indent(
            f'{info}\n\n{contents}\n' if contents else f'{info}\n', indent
        ),
        keep_markers=True,
    )

    # Calc which feature-sets are soft-required by any of the ones here
    # but not included here. For those we'll expose app-subsystems that
    # always return None.
    missing_soft_fset_names = set[str]()

    for fset in fsets.values():
        for softreq in fset.soft_requirements:
            if softreq not in fsets:
                missing_soft_fset_names.add(softreq)

    all_fset_names = missing_soft_fset_names | fsets.keys()

    # Add properties to instantiate feature-set subsystems.
    contents = ''

    for fsetname in sorted(all_fset_names):
        # for _fsname, fset in sorted(fsets.items()):
        if fsetname in missing_soft_fset_names:
            contents += (
                f'\n'
                f'@cached_property\n'
                f'def {fsetname}(self) -> Any | None:\n'
                f'    """Our {fsetname} subsystem (not available'
                f' in this project)."""\n'
                f'\n'
                f'    return None\n'
            )
        else:
            fset = fsets[fsetname]
            if fset.has_python_app_subsystem:
                if not fset.allow_as_soft_requirement:
                    raise CleanError(
                        f'allow_as_soft_requirement is False for'
                        f' feature-set {fset.name};'
                        f' this is not yet supported.'
                    )
                modname = fset.name_python_package
                classname = f'{fset.name_camel}Subsystem'
                contents += (
                    f'\n'
                    f'@cached_property\n'
                    f'def {fset.name}(self) -> {classname} | None:\n'
                    f'    """Our {fset.name} subsystem (if available)."""\n'
                    f'\n'
                    f'    try:\n'
                    f'        from {modname} import {classname}\n'
                    f'\n'
                    f'        return {classname}()\n'
                    f'    except ImportError:\n'
                    f'        return None\n'
                    f'    except Exception:\n'
                    f"        logging.exception('Error importing"
                    f" {modname}.')\n"
                    f'        return None\n'
                )
    out = replace_section(
        out,
        f'{indent}# __FEATURESET_APP_SUBSYSTEM_PROPERTIES_BEGIN__\n',
        f'{indent}# __FEATURESET_APP_SUBSYSTEM_PROPERTIES_END__\n',
        textwrap.indent(f'{info}\n{contents}\n', indent),
        keep_markers=True,
    )

    # Set default app-mode-selection logic.
    contents = (
        '# Hmm; need to think about how we auto-construct this; how\n'
        '# should we determine which app modes to check and in what\n'
        '# order?\n'
    )
    if 'scene_v1' in fsets:
        contents += (
            'import bascenev1\n'
            '\n'
            'if bascenev1.SceneV1AppMode.supports_intent(intent):\n'
            '    return bascenev1.SceneV1AppMode\n\n'
        )
    contents += (
        "raise RuntimeError(f'No handler found for"
        " intent {type(intent)}.')\n"
    )

    indent = '            '
    out = replace_section(
        out,
        f'{indent}# __DEFAULT_APP_MODE_SELECTION_BEGIN__\n',
        f'{indent}# __DEFAULT_APP_MODE_SELECTION_END__\n',
        textwrap.indent(f'{info}\n\n{contents}\n', indent),
        keep_markers=True,
    )

    # Note: we *should* format this string, but because this code
    # runs with every project update I'm just gonna try to keep the
    # formatting correct manually for now to save a bit of time.
    # (project update time jumps from 0.3 to 0.5 seconds if I enable
    # formatting here for just this one file).
    return out