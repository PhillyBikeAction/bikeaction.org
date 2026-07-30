from django.utils import timezone
from interactions import Extension, OptionType, SlashContext, slash_command, slash_option


class CommunityActionFundApplications(Extension):
    @slash_command(
        name="community-fund",
        description="Community Action Fund application commands",
        sub_cmd_name="decide",
        sub_cmd_description="Approve or decline the application in this thread",
    )
    @slash_option(
        name="decision",
        description="Enter approve or decline",
        required=True,
        opt_type=OptionType.STRING,
    )
    async def community_fund_decide(self, ctx: SlashContext, decision: str):
        from community_fund.models import CommunityActionFundApplication

        application = await CommunityActionFundApplication.objects.filter(
            thread_id=ctx.channel_id
        ).afirst()
        decision = decision.lower()
        if application is None:
            message = "Sorry, no Community Action Fund application is associated with this thread."
        elif application.decision:
            message = f"This application was already {application.get_decision_display().lower()}."
        elif decision not in {"approve", "decline"}:
            message = "Decision must be either `approve` or `decline`."
        else:
            application.decision = (
                CommunityActionFundApplication.Decision.APPROVED
                if decision == "approve"
                else CommunityActionFundApplication.Decision.DECLINED
            )
            application.decided_at = timezone.now()
            application.decided_by = str(ctx.member)
            await application.asave()
            message = f"Application marked {application.get_decision_display().lower()}."
            await ctx.channel.send(
                f"Community Action Fund application {application.get_decision_display().lower()} "
                f"by {ctx.member}."
            )

        await ctx.send(message, ephemeral=True)


def setup(bot):
    CommunityActionFundApplications(bot)
