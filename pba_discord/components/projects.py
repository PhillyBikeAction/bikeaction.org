from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.utils import timezone
from interactions import (
    Extension,
    OptionType,
    SlashContext,
    slash_command,
    slash_option,
)

from projects.tasks import (
    add_new_project_voting_message_and_thread,
    approve_new_project,
    archive_project,
)


class ProjectApplications(Extension):
    SELECTION_CHANNEL = settings.NEIGHBORHOOD_SELECTION_DISCORD_CHANNEL_ID

    def __init__(self, bot):
        self.bot = bot

    @slash_command(
        name="project",
        description="Project Application related commands",
        sub_cmd_name="archive",
        sub_cmd_description="Archive a completed project",
    )
    async def project_archive(self, ctx: SlashContext):
        from projects.models import ProjectApplication

        project_application = await ProjectApplication.objects.filter(
            channel_id=ctx.channel_id
        ).afirst()
        if project_application is None:
            msg = "Sorry, cannot find an associated project in the current channel."
        elif project_application.archived:
            msg = "Project already archived."
        else:
            msg = "On it!"
            project_application.archived_by = str(ctx.member)
            project_application.archived_at = timezone.now()
            project_application.archived = True
            await project_application.asave()
            archive_project.delay(project_application.id)

        await ctx.send(msg, ephemeral=True)

    @slash_command(
        name="project",
        description="Project Application related commands",
        sub_cmd_name="vote",
        sub_cmd_description="Send project to board for vote",
    )
    async def project_vote(self, ctx: SlashContext):
        from projects.models import ProjectApplication

        project_application = await ProjectApplication.objects.filter(
            thread_id=ctx.channel_id
        ).afirst()
        if project_application is None:
            msg = "Sorry, cannot find an associated project in the current channel/thread."
        elif project_application.voting_thread_id:
            msg = "Project application already sent for vote."
        elif project_application.archived:
            msg = "Project already archived."
        elif project_application.approved:
            msg = "Project already approved."
        else:
            msg = "On it!"
            project_application.vote_initiator = str(ctx.member)
            await project_application.asave()
            add_new_project_voting_message_and_thread.delay(project_application.id)
        await ctx.send(msg, ephemeral=True)

    @slash_command(
        name="project",
        description="Project Application related commands",
        sub_cmd_name="approve",
        sub_cmd_description="Approve a project after board vote",
    )
    @slash_option(
        name="project_channel_name",
        description="The name of the project channel to create, if needed",
        required=False,
        opt_type=OptionType.STRING,
    )
    @slash_option(
        name="project_mentor",
        description=(
            "The discord user name of the organizer who will Mentor the Project Lead, if needed"
        ),
        required=False,
        opt_type=OptionType.USER,
    )
    @slash_option(
        name="really_nothing",
        description="Use this option if you _do not_ want a channel or mentor",
        required=False,
        opt_type=OptionType.BOOLEAN,
    )
    async def project_approve(
        self,
        ctx: SlashContext,
        project_channel_name=None,
        project_mentor=None,
        really_nothing=False,
    ):
        if project_channel_name is None and project_mentor is None and not really_nothing:
            msg = (
                "You must either specify a project channel name and/or project mentor, "
                "OR set really_nothing to True!"
            )
            await ctx.send(msg, ephemeral=True)
            return

        from projects.models import ProjectApplication

        project_application = (
            await ProjectApplication.objects.filter(voting_thread_id=ctx.channel_id)
            .select_related("submitter")
            .afirst()
        )
        if project_application is None:
            msg = (
                "Sorry, cannot find an associated project application vote "
                "in the current channel/thread."
            )
        elif project_application.archived:
            msg = "Project already archived."
        elif project_application.approved:
            msg = "Project already approved."
        else:
            discord_account = await SocialAccount.objects.filter(
                user=project_application.submitter
            ).afirst()
            if discord_account:
                project_lead_id = discord_account.uid
            else:
                project_lead_id = None
            errors = []
            if project_channel_name and project_channel_name in [
                c.name for c in ctx.guild.channels
            ]:
                errors.append(
                    f"Cannot create Channel: Channel with name `{project_channel_name}` "
                    "already exists"
                )
            if project_channel_name and settings.ACTIVE_PROJECT_CATEGORY_ID is None:
                errors.append(
                    "Cannot create Channel: No Active Project Category ID configured in settings"
                )
            if project_mentor and project_mentor not in ctx.guild.members:
                errors.append(f"Cannot assign Mentor: No user {project_mentor} found!")
            if settings.ACTIVE_PROJECT_LEAD_ROLE_ID is None:
                errors.append(
                    "Cannot add Project Lead Role: No Project Lead Role ID configured in settings"
                )
            elif discord_account is None:
                errors.append(
                    "Cannot add Project Lead Role: No discord user found for Project Lead"
                )
            else:
                role = await ctx.guild.fetch_role(settings.ACTIVE_PROJECT_LEAD_ROLE_ID)
                if role is None:
                    errors.append(
                        "Cannot add Project Lead Role: No Project Lead Role with ID "
                        f"{settings.ACTIVE_PROJECT_LEAD_ROLE_ID} found!"
                    )
            if errors:
                msg = " :cry: **Sorry, there are some issues!** :cry: \n"
                msg += "Project approval could not be completed because:\n"
                for error in errors:
                    msg += f"- :exclamation: {error}\n"
            else:
                msg = "On it!"
                project_application.approved_by = str(ctx.member)
                project_application.approved_at = timezone.now()
                project_application.approved = True
                await project_application.asave()
                approve_new_project.delay(
                    project_application.id,
                    project_channel_name,
                    project_mentor.id if project_mentor else None,
                    project_lead_id,
                )
        await ctx.send(msg, ephemeral=True)


def setup(bot):
    ProjectApplications(bot)
