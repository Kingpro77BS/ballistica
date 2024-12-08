# To learn more, see https://ballistica.net/wiki/meta-tag-system
# ba_meta require api 8

from __future__ import annotations

from typing import TYPE_CHECKING

import babase
import random
import bascenev1 as bs
from bascenev1lib.game.hockey import Puck, Player, HockeyGame, PuckDiedMessage
from bascenev1lib.gameutils import SharedObjects
from bascenev1lib.actor.scoreboard import Scoreboard
from bascenev1lib.actor.powerupbox import PowerupBoxFactory
from bascenev1lib.actor.playerspaz import PlayerSpaz, PlayerSpazHurtMessage
from bascenev1lib.actor.spazfactory import SpazFactory

if TYPE_CHECKING:
	from typing import Any, Sequence


class NewPlayerSpaz(PlayerSpaz):

	def handlemessage(self, msg: Any) -> Any:
		if isinstance(msg, bs.HitMessage):
			source_player = msg.get_source_player(type(self._player))
			if source_player:
				self.last_player_attacked_by = source_player
				self.last_attacked_time = babase.apptime()
				self.last_attacked_type = (msg.hit_type, msg.hit_subtype)

			if not self.node:
				return None
			if self.node.invincible:
				SpazFactory.get().block_sound.play(
					1.0,
					position=self.node.position,
				)
				return True

			# If we were recently hit, don't count this as another.
			# (so punch flurries and bomb pileups essentially count as 1 hit)
			local_time = int(bs.time() * 1000.0)
			assert isinstance(local_time, int)
			if (
				self._last_hit_time is None
				or local_time - self._last_hit_time > 1000
			):
				self._num_times_hit += 1
				self._last_hit_time = local_time

			mag = msg.magnitude * self.impact_scale
			velocity_mag = msg.velocity_magnitude * self.impact_scale
			damage_scale = 0.22

			# If they've got a shield, deliver it to that instead.
			if self.shield:
				if msg.flat_damage:
					damage = msg.flat_damage * self.impact_scale
				else:
					# Hit our spaz with an impulse but tell it to only return
					# theoretical damage; not apply the impulse.
					assert msg.force_direction is not None
					self.node.handlemessage(
						'impulse',
						msg.pos[0],
						msg.pos[1],
						msg.pos[2],
						msg.velocity[0],
						msg.velocity[1],
						msg.velocity[2],
						mag,
						velocity_mag,
						msg.radius,
						1,
						msg.force_direction[0],
						msg.force_direction[1],
						msg.force_direction[2],
					)
					damage = damage_scale * self.node.damage

				assert self.shield_hitpoints is not None
				self.shield_hitpoints -= int(damage)
				self.shield.hurt = (
					1.0
					- float(self.shield_hitpoints) / self.shield_hitpoints_max
				)

				# Its a cleaner event if a hit just kills the shield
				# without damaging the player.
				# However, massive damage events should still be able to
				# damage the player. This hopefully gives us a happy medium.
				max_spillover = SpazFactory.get().max_shield_spillover_damage
				if self.shield_hitpoints <= 0:
					# FIXME: Transition out perhaps?
					self.shield.delete()
					self.shield = None
					SpazFactory.get().shield_down_sound.play(
						1.0,
						position=self.node.position,
					)

					# Emit some cool looking sparks when the shield dies.
					npos = self.node.position
					bs.emitfx(
						position=(npos[0], npos[1] + 0.9, npos[2]),
						velocity=self.node.velocity,
						count=random.randrange(20, 30),
						scale=1.0,
						spread=0.6,
						chunk_type='spark',
					)

				else:
					SpazFactory.get().shield_hit_sound.play(
						0.5,
						position=self.node.position,
					)

				# Emit some cool looking sparks on shield hit.
				assert msg.force_direction is not None
				bs.emitfx(
					position=msg.pos,
					velocity=(
						msg.force_direction[0] * 1.0,
						msg.force_direction[1] * 1.0,
						msg.force_direction[2] * 1.0,
					),
					count=min(30, 5 + int(damage * 0.005)),
					scale=0.5,
					spread=0.3,
					chunk_type='spark',
				)

				# If they passed our spillover threshold,
				# pass damage along to spaz.
				if self.shield_hitpoints <= -max_spillover:
					leftover_damage = -max_spillover - self.shield_hitpoints
					shield_leftover_ratio = leftover_damage / damage

					# Scale down the magnitudes applied to spaz accordingly.
					mag *= shield_leftover_ratio
					velocity_mag *= shield_leftover_ratio
				else:
					return True  # Good job shield!
			else:
				shield_leftover_ratio = 1.0

			if msg.flat_damage:
				damage = int(
					msg.flat_damage * self.impact_scale * shield_leftover_ratio
				)
			else:
				# Hit it with an impulse and get the resulting damage.
				assert msg.force_direction is not None
				if msg.hit_type != 'punch':
					self.node.handlemessage(
						'impulse',
						msg.pos[0],
						msg.pos[1],
						msg.pos[2],
						msg.velocity[0],
						msg.velocity[1],
						msg.velocity[2],
						mag,
						velocity_mag,
						msg.radius,
						0,
						msg.force_direction[0],
						msg.force_direction[1],
						msg.force_direction[2],
					)

				damage = int(damage_scale * self.node.damage)
			self.node.handlemessage('hurt_sound')

			# Play punch impact sound based on damage if it was a punch.
			if msg.hit_type == 'punch':
				if self.node.hold_node:
					self.node.hold_node = None
				damage = 0
				sound = SpazFactory.get().punch_sound
				sound.play(1.0, position=self.node.position)

				# Throw up some chunks.
				assert msg.force_direction is not None
				bs.emitfx(
					position=msg.pos,
					velocity=(
						msg.force_direction[0] * 0.5,
						msg.force_direction[1] * 0.5,
						msg.force_direction[2] * 0.5,
					),
					count=min(10, 1 + int(damage * 0.0025)),
					scale=0.3,
					spread=0.03,
				)

				bs.emitfx(
					position=msg.pos,
					chunk_type='sweat',
					velocity=(
						msg.force_direction[0] * 1.3,
						msg.force_direction[1] * 1.3 + 5.0,
						msg.force_direction[2] * 1.3,
					),
					count=min(30, 1 + int(damage * 0.04)),
					scale=0.9,
					spread=0.28,
				)

				# Momentary flash.
				hurtiness = damage * 0.003
				punchpos = (
					msg.pos[0] + msg.force_direction[0] * 0.02,
					msg.pos[1] + msg.force_direction[1] * 0.02,
					msg.pos[2] + msg.force_direction[2] * 0.02,
				)
				flash_color = (1.0, 0.0, 0.0)
				light = bs.newnode(
					'light',
					attrs={
						'position': punchpos,
						'radius': 0.12 + hurtiness * 0.12,
						'intensity': 0.3 * (1.0 + 1.0 * hurtiness),
						'height_attenuated': False,
						'color':flash_color,
					},
				)
				bs.timer(0.06, light.delete)

				flash = bs.newnode(
					'flash',
					attrs={
						'position': punchpos,
						'size': 0.17 + 0.17 * hurtiness,
						'color': flash_color,
					},
				)
				bs.timer(0.06, flash.delete)

			if msg.hit_type == 'impact':
				assert msg.force_direction is not None
				bs.emitfx(
					position=msg.pos,
					velocity=(
						msg.force_direction[0] * 2.0,
						msg.force_direction[1] * 2.0,
						msg.force_direction[2] * 2.0,
					),
					count=min(10, 1 + int(damage * 0.01)),
					scale=0.4,
					spread=0.1,
				)
			if self.hitpoints > 0:
				# It's kinda crappy to die from impacts, so lets reduce
				# impact damage by a reasonable amount *if* it'll keep us alive
				if msg.hit_type == 'impact' and damage > self.hitpoints:
					# Drop damage to whatever puts us at 10 hit points,
					# or 200 less than it used to be whichever is greater
					# (so it *can* still kill us if its high enough)
					newdamage = max(damage - 200, self.hitpoints - 10)
					damage = newdamage
				self.node.handlemessage('flash')

				# If we're holding something, drop it.
				if damage > 0.0 and self.node.hold_node:
					self.node.hold_node = None
				self.hitpoints -= damage
				self.node.hurt = (
					1.0 - float(self.hitpoints) / self.hitpoints_max
				)

				# If we're cursed, *any* damage blows us up.
				if self._cursed and damage > 0:
					bs.timer(
						0.05,
						bs.WeakCall(
							self.curse_explode, msg.get_source_player(bs.Player)
						),
					)

				# If we're frozen, shatter.. otherwise die if we hit zero
				if self.frozen and (damage > 200 or self.hitpoints <= 0):
					self.shatter()
				elif self.hitpoints <= 0:
					self.node.handlemessage(
						bs.DieMessage(how=bs.DeathType.IMPACT)
					)

			# If we're dead, take a look at the smoothed damage value
			# (which gives us a smoothed average of recent damage) and shatter
			# us if its grown high enough.
			if self.hitpoints <= 0:
				damage_avg = self.node.damage_smoothed * damage_scale
				if damage_avg >= 1000:
					self.shatter()

			activity = self._activity()
			if activity is not None and self._player.exists():
				activity.handlemessage(PlayerSpazHurtMessage(self))
		else:
			super().handlemessage(msg)


class Ball(Puck):

	def __init__(self, position: Sequence[float] = (0.0, 1.0, 0.0)):
		bs.Actor.__init__(self)
		shared = SharedObjects.get()
		activity = self.getactivity()

		# Spawn just above the provided point.
		self._spawn_pos = (position[0], position[0] + 1.2, position[0])
		self.last_players_to_touch: dict[int, Player] = {}
		self.scored = False
		assert activity is not None
		assert isinstance(activity, SoccerGame)
		pmats = [shared.object_material, activity.ball_material]
		mesh = bs.getmesh('frostyPelvis')
		texture = bs.gettexture('ouyaYButton')
		self.node = bs.newnode(
			'prop',
			delegate=self,
			attrs={
				'mesh': mesh,
				'color_texture': texture,
				'body': 'sphere',
				'reflection': None,
				'reflection_scale': [0.2],
				'shadow_size': 0.5,
				'is_area_of_interest': True,
				'gravity_scale': 1.018,
				'damping': 0.0002,
				'height_attenuated': True,
				'position': self._spawn_pos,
				'materials': pmats,
			},
		)
		bs.animate(self.node, 'mesh_scale', {0: 0, 0.2: 1.2, 0.26: 1})
		self.laser = bs.newnode(
			'locator',
			owner=self.node,
			attrs={
				'size': (0.2, 0.2, 0.2),
				'color': (1.0, 1.0, 0.0),
				'drawShadow': False,
				'shape': 'circle'
			},
		)
		self.ttt = bs.timer(0.01, bs.WeakCall(self.laser_set_y), repeat=True)

	def laser_set_y(self):
		if (self.laser.exists()):
			self.laser.position = (self.node.position[0], 0.1, self.node.position[2])

# ba_meta export bascenev1.GameActivity
class SoccerGame(HockeyGame):
	"""Football game for teams mode."""

	name = 'KNG Soccer'
	description = 'Football edited by Abdo'
	available_settings = [
		bs.IntSetting(
			'Score to Win',
			min_value=1,
			default=1,
			increment=1,
		),
		bs.IntChoiceSetting(
			'Time Limit',
			choices=[
				('None', 0),
				('1 Minute', 60),
				('2 Minutes', 120),
				('5 Minutes', 300),
				('10 Minutes', 600),
				('20 Minutes', 1200),
			],
			default=0,
		),
		bs.FloatChoiceSetting(
			'Respawn Times',
			choices=[
				('Shorter', 0.25),
				('Short', 0.5),
				('Normal', 1.0),
				('Long', 2.0),
				('Longer', 4.0),
			],
			default=1.0,
		),
		bs.BoolSetting('Boxing Gloves', default=False),
		bs.BoolSetting('Enable Powerups', default=False),
		bs.BoolSetting('Ice Floor', default=True),
		bs.BoolSetting('Hit Players', default=False),
		bs.BoolSetting('Epic Mode', default=False),
	]

	def __init__(self, settings: dict):
		super().__init__(settings)
		shared = SharedObjects.get()
		self._scoreboard = Scoreboard()
		self._cheer_sound = bs.getsound('cheer')
		self._chant_sound = bs.getsound('crowdChant')
		self._foghorn_sound = bs.getsound('foghorn')
		self._swipsound = bs.getsound('swip')
		self._whistle_sound = bs.getsound('refWhistle')
		self._boxing_gloves = bool(settings['Boxing Gloves'])
		self._enable_powerups = bool(settings['Enable Powerups'])
		self._ice_floor = bool(settings['Ice Floor'])
		self._hit_players = bool(settings['Hit Players'])
		self._epic_mode = bool(settings['Epic Mode'])

		# Base class overrides:
		self.slow_motion = self._epic_mode
		self.default_music = (bs.MusicType.EPIC
							  if self._epic_mode else bs.MusicType.FOOTBALL)
		
		self.ball_material = bs.Material()
		self.ball_material.add_actions(
			actions=('modify_part_collision', 'friction', 0.5),
		)
		self.ball_material.add_actions(
			conditions=('they_have_material', shared.pickup_material),
			actions=('modify_part_collision', 'collide', False),
		)
		self.ball_material.add_actions(
			conditions=(
				('we_are_younger_than', 100),
				'and',
				('they_have_material', shared.object_material),
			),
			actions=('modify_node_collision', 'collide', False),
		)

		# Keep track of which player last touched the puck
		self.ball_material.add_actions(
			conditions=('they_have_material', shared.player_material),
			actions=('call', 'at_connect', self._handle_puck_player_collide),
		)

		# We want the puck to kill powerups; not get stopped by them
		self.ball_material.add_actions(
			conditions=('they_have_material',
						PowerupBoxFactory.get().powerup_material),
			actions=(
				('modify_part_collision', 'physical', True),
				('message', 'their_node', 'at_connect', bs.DieMessage()),
			),
		)
		self._score_region_material = bs.Material()
		self._score_region_material.add_actions(
			conditions=('they_have_material', self.ball_material),
			actions=(
				('modify_part_collision', 'collide', True),
				('modify_part_collision', 'physical', False),
				('call', 'at_connect', self._handle_score),
			),
		)
		self._puck_spawn_pos: Sequence[float] | None = None
		self._score_regions: list[bs.NodeActor] | None = None
		self._puck: Ball | None = None
		self._score_to_win = int(settings['Score to Win'])
		self._time_limit = float(settings['Time Limit'])

	def on_transition_in(self) -> None:
		super().on_transition_in()
		shared = SharedObjects.get()
		activity = bs.getactivity()
		if self._ice_floor:
			activity.map.is_hockey = True
		else:
			activity.map.is_hockey = False
			activity.globalsnode.floor_reflection = True
		activity.map.node.materials = [shared.footing_material]
		activity.map.floor.materials = [shared.footing_material]
		activity.map.floor.color = (0.0, 0.63, 0.0)

	def on_begin(self) -> None:

		self.setup_standard_time_limit(self._time_limit)
		if self._enable_powerups:
			self.setup_standard_powerup_drops()
		else:
			pass
		self._puck_spawn_pos = self.map.get_flag_position(None)
		self._spawn_puck()

		main_text = bs.newnode('text', attrs={'text': "KNG Soccer",
								  'position': (0, 200),
							  	'scale': 1.3,
							  	'opacity': 0.0,
							  	'big': True,
					  			'color': (1, 1, 1),
					  			'shadow': 1.5,
						  		'flatness': 0.5,
								  'h_align': 'center',
						  		'v_align': 'top'
						})
		description_text = bs.newnode('text', attrs={'text': "Have Fun with us(:",
								  'position': (0, 150),
								  'scale': 1.25,
								  'opacity': 0.0,
								  'color': (0.5, 0.5, 0.5),
								  'shadow': 0.7,
								  'flatness': 0.6,
								  'h_align': 'center',
								  'v_align': 'top'
						})

		fade_in_duration = 1.0
		display_duration = 2.0
		fade_out_duration = 1.0
		bs.animate(main_text, 'opacity', {0: 0.0, fade_in_duration: 1.0})
		bs.animate(description_text, 'opacity', {0: 0.0, fade_in_duration: 1.0})
		bs.timer(fade_in_duration + display_duration, lambda: bs.animate(main_text, 'opacity', {0: 1.0, fade_out_duration: 0.0}))
		bs.timer(fade_in_duration + display_duration, lambda: bs.animate(description_text, 'opacity', {0: 1.0, fade_out_duration: 0.0}))
		total_duration = fade_in_duration + display_duration + fade_out_duration
		bs.timer(total_duration, lambda: main_text.delete())
		bs.timer(total_duration, lambda: description_text.delete())

		def emit_snow_effect():
			bs.emitfx(
    			position=(random.uniform(-10, 10), 5, random.uniform(-10, 10)),
   			 velocity=(0, -0.1, 0),
    			count=5,
   			 scale=1,
 			   spread=0.3,
   			 chunk_type='spark',
			)

		bs.timer(0.01, emit_snow_effect, repeat=True)


		# Set up the two score regions.
		defs = self.map.defs
		self._score_regions = []
		self._score_regions.append(
			bs.NodeActor(
				bs.newnode(
					'region',
					attrs={
						'position': defs.boxes['goal1'][0:3],
						'scale': defs.boxes['goal1'][6:9],
						'type': 'box',
						'materials': [self._score_region_material],
					},
				)
			)
		)
		light = bs.newnode(
			'light',
				attrs={
					'position': (-0.07855, 0.475748, -5.13732),
					'radius': 0.15599,
					'intensity': 1.47999,
					'height_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
			)
		light = bs.newnode(
			'light',
				attrs={
					'position': (-1.48431, 0.473476, -5.15572),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (-2.8570526, 0.3019098, -5.1239796),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (-4.1308, 0.483785, -5.13377),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (-5.5349, 0.468279, -5.14534),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (-6.66312, 0.466822, -5.18042),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (-8.04724, 0.497461, -5.14312),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (-9.34372, 0.469157, -5.14848),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (-10.9187, 0.478126, -5.12876),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (-11.7742, 0.52921, -4.84556),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (-12.0269, 0.495267, -3.74063),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (-11.9906, 0.492509, -1.86828),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (-11.999, 0.471828, -0.33403),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (-11.9777, 0.455282, 1.38519),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (-12.0157, 0.441332, 3.052095),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (-11.718, 0.473994, 4.731501),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (1.178109, 0.498819, -5.13002),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (2.511056, 0.48218, -5.14052),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (3.845097, 0.479815, -5.18743),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (5.108961, 0.466952, -5.13494),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (6.46797, 0.476306, -5.14522),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (7.821037, 0.473988, -5.08184),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (9.13296, 0.493179, -5.15481),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (10.3236, 0.490237, -5.1058),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (11.54289, 0.463303, -4.68162),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (11.92094, 0.466818, -3.30562),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (11.90482, 0.447345, -2.1751),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (11.94508, 0.452326, -1.04594),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (11.8743, 0.482457, 0.078493),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (11.91155, 0.448188, 1.33588),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (11.90663, 0.484103, 2.589273),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (11.85477, 0.457702, 3.898435),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		light = bs.newnode(
			'light',
				attrs={
					'position': (10.69756, 0.475233, 5.078207),
					'radius': 0.15599,
					'intensity': 1.47999,
					'heghit_attenuated': False,
					'color':(0.0,0.5,1.0),
				},
		 )
		self._score_regions.append(
			bs.NodeActor(
				bs.newnode(
					'region',
					attrs={
						'position': defs.boxes['goal2'][0:3],
						'scale': defs.boxes['goal2'][6:9],
						'type': 'box',
						'materials': [self._score_region_material],
					},
				)
			)
		)
		self._update_scoreboard()
		self._chant_sound.play()

	def spawn_player(self, player: Player) -> bs.Actor:
		from bascenev1._coopsession import CoopSession
		if isinstance(self.session, bs.DualTeamSession):
			position = self.map.get_start_position(player.team.id)
		else:
			# otherwise do free-for-all spawn locations
			position = self.map.get_ffa_start_position(self.players)
		angle = None

		name = player.getname()
		color = player.color
		highlight = player.highlight

		light_color = babase.normalized_color(color)
		display_color = babase.safecolor(color, target_intensity=0.5)

		if self._hit_players:
			spaz = PlayerSpaz(
				color=color,
				highlight=highlight,
				character=player.character,
				player=player,
			)
		else:
			spaz = NewPlayerSpaz(
				color=color,
				highlight=highlight,
				character=player.character,
				player=player,
			)

		player.actor = spaz
		assert spaz.node

		spaz.node.name = name
		spaz.impact_scale = 0
		spaz.node.name_color = display_color
		spaz.connect_controls_to_player(enable_pickup=False)

		# Move to the stand position and add a flash of light.
		spaz.handlemessage(
			bs.StandMessage(
				position, angle if angle is not None else random.uniform(0, 360)
			)
		)
		self._spawn_sound.play(1, position=spaz.node.position)
		light = bs.newnode('light', attrs={'color': light_color})
		spaz.node.connectattr('position', light, 'position')
		bs.animate(light, 'intensity', {0: 0, 0.25: 1, 0.5: 0})
		bs.timer(0.5, light.delete)

		# custom
		if self._boxing_gloves:
			spaz.equip_boxing_gloves()

		return spaz

	def _spawn_puck(self) -> None:
		self._swipsound.play()
		self._whistle_sound.play()
		self._flash_puck_spawn()
		assert self._puck_spawn_pos is not None
		self._puck = Ball(position=self._puck_spawn_pos)

	def _handle_score(self) -> None:
		assert self._puck is not None
		assert self._score_regions is not None

		# Our puck might stick around for a second or two
		# we don't want it to be able to score again.
		if self._puck.scored:
			return

		region = bs.getcollision().sourcenode
		index = 0
		for index, score_region in enumerate(self._score_regions):
			if region == score_region.node:
				break

		for team in self.teams:
			if team.id == index:
				scoring_team = team
				team.score += 1

				# Tell all players to celebrate.
				for player in team.players:
					if player.actor:
						player.actor.handlemessage(bs.CelebrateMessage(3.0))
				e = bs.newnode('explosion',attrs={'position': self.map.defs.boxes['goal1'][0:3] if index==0 else self.map.defs.boxes['goal2'][0:3],
												  'radius': 7,
												  'color':(1.0,0.25,0.0) if index==0 else (1.0,0.0,0.4)
								})
				print(dir(e))
				bs.timer(4, e.delete)
				text = bs.newnode('text',attrs={'text': f"Goalscorer : {player.getname()}",        
												  'position': (0, -300, 0),
       										   'scale': 1.59,
      										    'color': (0, 1, 0),
   										       'shadow': 5.0,
    										      'flatness': 0.2,
      										    'h_align': 'center',
      										    'outline': True,
      										    'outline_color': (1, 1, 0),
      										    'outline_opacity': 5.0
								})
				bs.timer(4, text.delete)

				def move_text_up():
					if text.exists():
						pos = text.position
						text.position = (pos[0], pos[1] + 0.88, pos[2])
				def fade_text():
					if text.exists():
						text.opacity = max(0, text.opacity - 0.03)
						if text.opacity <=0:
							text.delete()
				def emit_effect():
					if text.exists():
						bs.emitfx(
    						position=self.map.defs.boxes['goal1'][0:3] if index==0 else self.map.defs.boxes['goal2'][0:3],
   						 velocity=(0, 2, 0),
    						count=20,
   						 scale=1.5,
 						   spread=2,
   						 chunk_type='shrapnel',
						)
				bs.timer(0.001, move_text_up, repeat=True)
				bs.timer(0.03, fade_text, repeat=True)
				bs.timer(0.1, emit_effect, repeat=True)


				# If we've got the player from the scoring team that last
				# touched us, give them points.
				if (
					scoring_team.id in self._puck.last_players_to_touch
					and self._puck.last_players_to_touch[scoring_team.id]
				):
					self.stats.player_scored(
						self._puck.last_players_to_touch[scoring_team.id],
						100,
						big_message=False,
					)


				# End game if we won.
				if team.score >= self._score_to_win:
					self.end_game()

		self._foghorn_sound.play()
		self._cheer_sound.play()

		self._puck.scored = True

		# Kill the puck (it'll respawn itself shortly).
		bs.timer(1.0, self._kill_puck)

		light = bs.newnode(
			'light',
			attrs={
				'position': bs.getcollision().position,
				'height_attenuated': True,
				'color': (1.0, 0.0, 0.0),
			},
		)
		bs.animate(light, 'intensity', {0: 0, 0.5: 1, 1.0: 0}, loop=True)
		bs.timer(0.2, light.delete)

		bs.cameraflash(duration=10.0)
		self._update_scoreboard()

		old_mesh_scale = self._puck.node.mesh_scale
		bs.animate(self._puck.node, 'mesh_scale', {
			0.2: old_mesh_scale,
			0.3: old_mesh_scale * 1.2,
			0.4: old_mesh_scale,
			0.5: old_mesh_scale * 1.2,
			0.6: old_mesh_scale,
			0.7: old_mesh_scale * 1.2,
			0.8: old_mesh_scale,
			0.9: old_mesh_scale * 1.2,
			1.0: old_mesh_scale * 0,
		})