from django import template
from django.template import Variable, NodeList
from django.contrib.auth.models import Group
from django.template import Node

from uuid import uuid4

register = template.Library()

@register.tag()
def ifusergroup(parser, token):
    """ Check to see if the currently logged in user belongs to one or more groups
    Requires the Django authentication contrib app and middleware.
 
    Usage: {% ifusergroup Admins %} ... {% endifusergroup %}, or
           {% ifusergroup Admins Clients Programmers Managers %} ... {% else %} ... {% endifusergroup %}

           Multi-word user groups: {% ifusergroup 'Pizza Party' %} ... {% endifusergroup %}
 
    """
    try:
        tokensp = token.split_contents()
        groups = []
        groups += tokensp[1:]
    except ValueError:
        raise template.TemplateSyntaxError("Tag 'ifusergroup' requires at least 1 argument.")
 
    nodelist_true = parser.parse(('else', 'endifusergroup'))
    token = parser.next_token()
 
    if token.contents == 'else':
        nodelist_false = parser.parse(('endifusergroup',))
        parser.delete_first_token()
    else:
        nodelist_false = NodeList()
 
    return GroupCheckNode(groups, nodelist_true, nodelist_false)


class SupercookieNode(Node):
    def render(self, context):
        cookie = uuid4().hex
        return cookie

@register.tag
def gen_supercookie(p,k):
    return SupercookieNode()
 
 
class GroupCheckNode(template.Node):
    def __init__(self, groups, nodelist_true, nodelist_false):
        self.groups = groups
        self.nodelist_true = nodelist_true
        self.nodelist_false = nodelist_false
 
    def render(self, context):
        user = Variable('user').resolve(context)
 
        if not user.is_authenticated():
            return self.nodelist_false.render(context)
 
        allowed = False
        for checkgroup in self.groups:
 
            if checkgroup.startswith('"') and checkgroup.endswith('"'):
                checkgroup = checkgroup[1:-1]
 
            if checkgroup.startswith("'") and checkgroup.endswith("'"):
                checkgroup = checkgroup[1:-1]
 
            try:
                group = Group.objects.get(name=checkgroup)
            except Group.DoesNotExist:
                break
 
            if group in user.groups.all():
                allowed = True
                break
 
        if allowed:
            return self.nodelist_true.render(context)
        else:
            return self.nodelist_false.render(context)
